"""Reader and writer for the G1X Four effect file system
(flash 0x102000-0x400000, 766 blocks of 4 KB).

Format, decoded from the factory image in Zoom's updater (resource 136) and
checked against the files read from a real pedal (tools/g1fs_test.py):
  - block 0: 55 AA 00 01 04 00 FF 00 <u16 number of blocks>;
  - directory blocks (factory image: 3, 5, 7, 9): <u8 seq> A5 <u16 cursor>
    <live> FF FF FF, then 32-byte slots up to the first all-FF slot:
        <u16 first data index> 01 <state> <u32 size> <name[12] NUL-padded> FF*12
    state FF = valid file, 00 = deleted. Old directory copies have <live>
    programmed from FF to 00; exactly one keeps FF. <cursor> is the data
    index of the last block allocated: the file system writes forward from
    cursor + 1, reusing (erasing) stale blocks in turn;
  - data index i lives in physical block i + 10: <u16 prev> <u16 next>
    <u16 bytes used> payload (<= 4090 bytes); FFFF = none.
Usage:  python tools/g1fs.py list <image>
        python tools/g1fs.py extract <image> <outdir>
"""
import struct
import sys
from pathlib import Path

BLOCK = 4096
DATA_BASE = 10
PAYLOAD = BLOCK - 6
SLOTS = (BLOCK - 8) // 32
EMPTY = b"\xff" * 32


def blocks(img):
    return [img[i:i + BLOCK] for i in range(0, len(img), BLOCK)]


def _slots(blk):
    """Directory slots up to the first empty one: (name, first, size, valid, raw)."""
    out = []
    for k in range(SLOTS):
        e = bytes(blk[8 + 32 * k:8 + 32 * (k + 1)])
        if e == EMPTY:
            break
        first, = struct.unpack_from("<H", e, 0)
        size, = struct.unpack_from("<I", e, 4)
        name = e[8:20].split(b"\x00")[0].split(b"\xff")[0].decode("latin-1")
        out.append((name, first, size, e[3] == 0xFF, e))
    return out


def directories(img):
    """All directory blocks: (physical block, seq, valid entries, live, cursor)."""
    out = []
    for b, blk in enumerate(blocks(img)):
        if blk[1] != 0xA5 or blk[5:8] != b"\xff\xff\xff" or blk[4] not in (0x00, 0xFF):
            continue
        ents = [(n, f, sz, s[2:4], s[20:32]) for n, f, sz, ok, s in _slots(blk) if ok]
        out.append((b, blk[0], ents, blk[4] == 0xFF, struct.unpack_from("<H", blk, 2)[0]))
    return out


def current_dir(img):
    """The live directory (byte 4 still FF): (block, seq, valid entries)."""
    live = [d for d in directories(img) if d[3]]
    if len(live) != 1:
        raise ValueError("%d live directories" % len(live))
    return live[0][:3]


def read_file(img, first, size):
    out, idx, prev, seen = bytearray(), first, 0xFFFF, set()
    while idx != 0xFFFF:
        if idx in seen:
            raise ValueError("chain loop at %d" % idx)
        seen.add(idx)
        blk = img[(idx + DATA_BASE) * BLOCK:(idx + DATA_BASE + 1) * BLOCK]
        p, nxt, used = struct.unpack_from("<HHH", blk, 0)
        if p != prev:
            raise ValueError("chain back-link %d != %d at %d" % (p, prev, idx))
        out += blk[6:6 + used]
        prev, idx = idx, nxt
    if len(out) != size:
        raise ValueError("size %d != directory size %d" % (len(out), size))
    return bytes(out)


def _chain(img, first):
    idx, out = first, []
    while idx != 0xFFFF:
        out.append(idx)
        idx = struct.unpack_from("<H", img, (idx + DATA_BASE) * BLOCK + 2)[0]
    return out


def build_image(base, add=None, remove=(), replace=None):
    """A new image from `base` (the factory image), as the file system itself
    would leave it:
      remove   names marked deleted (slot state 00), their blocks freed
      replace  {name: bytes} rewritten in place (same size, same chain)
      add      {name: bytes} new files, allocated forward from the cursor and
               appended to the live directory; the cursor moves to the last
               block written
    Blocks not referenced by a valid entry are erased (FF): the region is
    erased and written whole, and the file system treats them as free.
    Everything else is kept byte for byte."""
    add, replace = dict(add or {}), dict(replace or {})
    img = bytearray(base)
    dblk, _, _ = current_dir(img)
    off = dblk * BLOCK
    slots = _slots(img[off:off + BLOCK])
    valid = [s[0] for s in slots if s[3]]
    for n in list(add) + list(remove) + list(replace):
        if len(n) > 12:
            raise ValueError("name too long: " + n)
    for n in list(remove) + list(replace):
        if n not in valid:
            raise ValueError("not on the image: " + n)
    for n in add:
        if n in valid and n not in remove:
            raise ValueError("already present: " + n)
    if len(slots) + len(add) > SLOTS:
        raise ValueError("directory full")
    ndata = len(img) // BLOCK - DATA_BASE
    used = set()
    for name, first, size, ok, _ in slots:
        if ok and name not in remove:
            used.update(_chain(img, first))
    for i in range(ndata):                             # free = erased
        if i not in used:
            img[(i + DATA_BASE) * BLOCK:(i + DATA_BASE + 1) * BLOCK] = b"\xff" * BLOCK
    for name, first, size, ok, _ in slots:             # in-place rewrites
        if ok and name in replace:
            data = replace[name]
            if len(data) != size:
                raise ValueError("replace %s must keep its size" % name)
            for k, idx in enumerate(_chain(img, first)):
                o = (idx + DATA_BASE) * BLOCK
                n_used = struct.unpack_from("<H", img, o + 4)[0]
                img[o + 6:o + 6 + n_used] = data[k * PAYLOAD:k * PAYLOAD + n_used]
    cursor = struct.unpack_from("<H", img, off + 2)[0]
    free = [i for i in ((cursor + 1 + j) % ndata for j in range(ndata)) if i not in used]
    new_slots = []
    for name, data in add.items():
        n = max(1, -(-len(data) // PAYLOAD))
        if n > len(free):
            raise ValueError("no space for " + name)
        ch, free = free[:n], free[n:]
        for k, idx in enumerate(ch):
            chunk = data[k * PAYLOAD:(k + 1) * PAYLOAD]
            o = (idx + DATA_BASE) * BLOCK
            struct.pack_into("<HHH", img, o, ch[k - 1] if k else 0xFFFF,
                             ch[k + 1] if k + 1 < n else 0xFFFF, len(chunk))
            img[o + 6:o + 6 + len(chunk)] = chunk
        cursor = ch[-1]
        new_slots.append(struct.pack("<HBBI", ch[0], 1, 0xFF, len(data))
                         + name.encode("latin-1").ljust(12, b"\x00") + b"\xff" * 12)
    body = b""
    for name, first, size, ok, raw in slots:
        if ok and name in remove:
            raw = raw[:3] + b"\x00" + raw[4:]
        body += raw
    body += b"".join(new_slots)
    struct.pack_into("<H", img, off + 2, cursor)
    img[off + 8:off + BLOCK] = body + b"\xff" * (BLOCK - 8 - len(body))
    return bytes(img)


def check_image(img, expect):
    """Re-read `img`; require exactly the files `expect` {name: bytes}, no
    block shared between files, and the cursor on an allocated block."""
    dblk, _, ents = current_dir(img)
    got = {name: read_file(img, first, size) for name, first, size, _, _ in ents}
    if set(got) != set(expect):
        raise ValueError("file set differs: %s" % (set(got) ^ set(expect)))
    for n, d in expect.items():
        if got[n] != d:
            raise ValueError("content differs: " + n)
    seen = {}
    for name, first, size, _, _ in ents:
        for idx in _chain(img, first):
            if idx in seen:
                raise ValueError("block %d shared by %s and %s" % (idx, seen[idx], name))
            seen[idx] = name
    cursor = struct.unpack_from("<H", img, dblk * BLOCK + 2)[0]
    if cursor not in seen:
        raise ValueError("cursor %d is not an allocated block" % cursor)
    return len(ents)


def main(argv):
    img = open(argv[1], "rb").read()
    b, seq, ents = current_dir(img)
    if argv[0] == "list":
        print("directory block %d, seq %#x, %d files" % (b, seq, len(ents)))
        for name, first, size, _, _ in ents:
            print("%-14s first %4d size %7d" % (name, first, size))
    elif argv[0] == "extract":
        out = Path(argv[2])
        out.mkdir(parents=True, exist_ok=True)
        for name, first, size, _, _ in ents:
            (out / name).write_bytes(read_file(img, first, size))
        print("extracted %d files to %s" % (len(ents), out))


if __name__ == "__main__":
    main(sys.argv[1:])

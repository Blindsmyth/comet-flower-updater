import click
from pathlib import Path
from .elfinfo import EM_TI_C6000, parse_effect_elf, reloc_names
from .models import ZD2Patch
from .parser import parse_zd2

@click.group()
def main() -> None:
    """Tooling for Zoom .ZD2 patch files."""
    pass

@main.command()
@click.argument('file_path', type=click.Path(exists=True))
def inspect(file_path: str) -> None:
    """Inspect a .ZD2 file and print its header and blocks."""
    path = Path(file_path)
    with path.open('rb') as f:
        data = f.read()
    
    try:
        patch = parse_zd2(data)
        
        click.echo(f"File: {path.name}")
        click.echo("-" * 40)
        click.echo(f"Magic:        {patch.header.magic}")
        click.echo(f"Checksum:     0x{patch.header.checksum:08X}")
        click.echo(f"Version:      {patch.header.version}")
        click.echo(f"Group ID:     {patch.header.group_id}")
        click.echo(f"Effect ID:    0x{patch.header.effect_id:08X}")
        click.echo(f"Effect Name:  {patch.header.name}")
        click.echo(f"Group Name:   {patch.header.group_name}")
        click.echo(f"Target:       0x{patch.header.target:08X}")
        click.echo(f"CRC valid:    {patch.crc_ok}")
        info = patch.info
        if info:
            click.echo(f"INFO:         class {info.word0}, "
                       f"'{info.group_text}', dspload {info.dspload:.2f}")
        click.echo(f"Trailer:      {patch.trailer.hex()}")
        click.echo("-" * 40)
        click.echo(f"Blocks found: {len(patch.blocks)}")
        for i, block in enumerate(patch.blocks):
            click.echo(f"  {i+1}. {block.tag} ({block.length} bytes)")
        data_block = patch.get_block("DATA")
        if data_block:
            elf = parse_effect_elf(data_block.data)
            click.echo("-" * 40)
            click.echo(f"ELF entry:    {elf.entry_symbol or hex(elf.entry)}"
                       f"{'' if elf.machine == EM_TI_C6000 else ' (NOT C6000!)'}")
            click.echo(f"Relocations:  {reloc_names(elf.reloc_types)}")
            for prm in elf.params:
                click.echo(f"  param {prm.name:<12} max {prm.max:<10} "
                           f"default {prm.default:<4} flags 0x{prm.flags:02x} "
                           f"{prm.handler}")
            for w, h, ptr in elf.images:
                click.echo(f"  image {w}x{h} @ 0x{ptr:08x}")
            
    except Exception as e:
        click.echo(f"Error parsing file: {e}", err=True)

@main.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--out-dir', '-o', default='extracted', help='Directory to save blocks')
def extract(file_path: str, out_dir: str) -> None:
    """Extract all blocks from a .ZD2 file as individual files."""
    path = Path(file_path)
    with path.open('rb') as f:
        data = f.read()
    
    try:
        patch = parse_zd2(data)
        out_path = Path(out_dir) / path.stem
        out_path.mkdir(parents=True, exist_ok=True)
        
        click.echo(f"Extracting blocks to {out_path}...")
        
        for block in patch.blocks:
            ext = ".bin"
            if block.tag in ["PRMJ", "TXE1", "TXJ1"]:
                ext = ".txt"
            elif block.tag == "DATA":
                ext = ".elf"
            
            block_file = out_path / f"{block.tag}{ext}"
            with block_file.open('wb') as f_out:
                f_out.write(block.data)
            click.echo(f"  - Saved {block.tag}{ext}")
            
    except Exception as e:
        click.echo(f"Error extracting blocks: {e}", err=True)

def _audit_row(path: Path, patch: ZD2Patch) -> str:
    h = patch.header
    info = patch.info
    icon = patch.get_block("ICON")
    icon_desc = "-"
    if icon and icon.data[:2] == b"BM" and len(icon.data) >= 26:
        w = int.from_bytes(icon.data[18:22], "little")
        ht = int.from_bytes(icon.data[22:26], "little")
        icon_desc = f"bmp{w}x{ht}"
    elif icon:
        icon_desc = f"raw{icon.length}"
    elf_desc = "-"
    data_block = patch.get_block("DATA")
    if data_block:
        elf = parse_effect_elf(data_block.data)
        imgs = "+".join(f"{w}x{ht}" for w, ht, _ in elf.images) or "none"
        elf_desc = f"{len(elf.params)}p {reloc_names(elf.reloc_types)} img:{imgs}"
    hdr_nz = sum(1 for b in h.unknown if b)
    return (f"{path.name:<14} {h.effect_id:08x} {h.version:<5} "
            f"t={h.target:04x} hdrNZ={hdr_nz:<2} crc={'ok' if patch.crc_ok else 'BAD'} "
            f"load={info.dspload if info else 0:6.2f} icon={icon_desc:<10} "
            f"trl={'zero' if not any(patch.trailer) else 'set '} {elf_desc}")


@main.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
def audit(directory: str) -> None:
    """One line per .ZD2 in DIRECTORY: identity, target, CRC, load, icon,
    trailer and ELF shape. Used to find the invariants of a pedal family."""
    files = sorted(p for p in Path(directory).rglob("*") if p.suffix.upper() == ".ZD2")
    for path in files:
        try:
            click.echo(_audit_row(path, parse_zd2(path.read_bytes())))
        except Exception as e:
            click.echo(f"{path.name:<14} ERROR {e}")
    click.echo(f"{len(files)} files")


@main.command(name="g1-retarget")
@click.argument('src', type=click.Path(exists=True, dir_okay=False))
@click.argument('dst', type=click.Path(dir_okay=False))
@click.option('--label', required=True, help='Up to 5 characters drawn on the icon')
@click.option('--pic', default=None,
              help='Slot picture text, up to two lines split by "/", e.g. GREEN/808')
def g1_retarget(src: str, dst: str, label: str, pic: str) -> None:
    """Convert a stomphacks DIY ZD2 into G1 Four container form."""
    from .g1 import retarget_g1
    out = retarget_g1(Path(src).read_bytes(), label,
                      pic.split("/") if pic else None)
    Path(dst).write_bytes(out)
    click.echo(_audit_row(Path(dst), parse_zd2(out)))


if __name__ == '__main__':
    main()

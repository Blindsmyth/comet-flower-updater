import pytest
from pathlib import Path
from click.testing import CliRunner
from zd2tools.cli import main
from zd2tools.elfinfo import parse_effect_elf
from zd2tools.parser import parse_zd2, zd2_crc

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> bytes:
    path = FIXTURES / name
    if not path.exists():
        pytest.skip(f"{name} not supplied (Zoom files are not redistributed)")
    return path.read_bytes()


def test_parse_nyc_muff():
    patch = parse_zd2(load("NYC_MUFF.ZD2"))

    assert patch.header.magic == "ZDLF"
    assert patch.header.version == "1.40"
    assert patch.header.name == "NYC Muff"
    assert patch.header.group_name == "DRIVE"
    assert patch.header.group_id == 3
    assert patch.header.effect_id == 0x030000D0
    assert patch.header.target == 0x7
    assert patch.crc_ok

    assert [b.tag for b in patch.blocks] == [
        "ICON", "TXJ1", "TXE1", "INFO", "DATA", "PRMJ", "PRME"]
    info = patch.info
    assert info is not None
    assert info.group_text == "DRVDRIVE"
    assert info.dspload == pytest.approx(34.86, abs=0.01)
    assert len(patch.trailer) == 16


def test_crc_detects_corruption():
    data = bytearray(load("NYC_MUFF.ZD2"))
    assert parse_zd2(bytes(data)).crc_ok
    data[0x200] ^= 0xFF
    assert not parse_zd2(bytes(data)).crc_ok
    # rewriting the stored checksum makes it valid again
    data[8:12] = zd2_crc(bytes(data)).to_bytes(4, "little")
    assert parse_zd2(bytes(data)).crc_ok


def test_effect_elf_nyc_muff():
    elf = parse_effect_elf(parse_zd2(load("NYC_MUFF.ZD2")).get_block("DATA").data)

    assert elf.machine == 140
    assert elf.entry_symbol == "Dll_NycMuff"
    assert elf.reloc_types == [1, 9, 10]
    assert [p.name for p in elf.params] == [
        "OnOff", "NYC Muff", "SUSTN", "Tone", "BAL", "VOL"]
    vol = elf.params[-1]
    assert (vol.max, vol.default, vol.flags) == (100, 58, 0x16)
    assert [(w, h) for w, h, _ in elf.images] == [(23, 32), (20, 10)]


def test_effect_elf_thevibe():
    elf = parse_effect_elf(parse_zd2(load("THEVIBE.ZD2")).get_block("DATA").data)

    assert [p.name for p in elf.params] == [
        "OnOff", "TheVibe", "Speed", "Depth", "Mode", "VOL"]
    assert [(w, h) for w, h, _ in elf.images] == [(23, 30), (20, 10), (24, 22)]


def test_audit_lists_fixtures():
    load("NYC_MUFF.ZD2")
    result = CliRunner().invoke(main, ["audit", str(FIXTURES)])
    assert result.exit_code == 0
    assert "NYC_MUFF.ZD2   030000d0" in result.output
    assert "crc=ok" in result.output


def test_g1_retarget_matches_stock_conventions():
    from zd2tools.g1 import G1_TARGET, icon_bmp, retarget_g1
    src = load("THEVIBE.ZD2")
    out = parse_zd2(retarget_g1(src, "TEST"))

    assert out.crc_ok
    assert out.header.target == G1_TARGET
    assert out.header.unknown[0] == 0x01                 # 0x10
    assert out.header.unknown[0x18 - 0x10] == 0x80
    assert out.header.unknown[0x58 - 0x10] == 0x01       # slot count
    assert out.trailer == bytes(16)
    assert out.info.group_text == "MODMOD."
    icon = out.get_block("ICON").data
    assert len(icon) == 182 and icon[:2] == b"BM"
    assert icon == icon_bmp("TEST")
    # DATA and parameter text pass through untouched
    orig = parse_zd2(src)
    for tag in ("DATA", "PRMJ", "PRME", "TXE1"):
        assert out.get_block(tag).data == orig.get_block(tag).data


def test_icon_header_matches_stock():
    from zd2tools.g1 import icon_bmp
    stock = parse_zd2(load("NYC_MUFF.ZD2")).get_block("ICON").data
    mine = icon_bmp("X", width=23)
    assert len(mine) == len(stock)
    assert mine[:62] == stock[:62]       # same BMP/DIB header and palette


def test_slot_picture_page_format():
    from zd2tools.g1 import slot_pic_bytes, slot_pic_pixels
    pic = slot_pic_bytes(["GREEN", "808"])
    px = slot_pic_pixels(["GREEN", "808"])
    assert len(pic) == 92                          # 4 pages x 23 columns
    for y in (0, 5, 13, 29):
        for x in (0, 4, 11, 22):
            assert bool(pic[(y // 8) * 23 + x] >> (y % 8) & 1) == bool(px[y][x])

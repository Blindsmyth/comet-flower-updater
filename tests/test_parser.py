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

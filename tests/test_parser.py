import pytest
from pathlib import Path
from zd2tools.parser import parse_zd2

def test_parse_nyc_muff():
    fixture_path = Path(__file__).parent / "fixtures" / "NYC_MUFF.ZD2"
    with fixture_path.open('rb') as f:
        data = f.read()
    
    patch = parse_zd2(data)
    
    assert patch.header.magic == "ZDLF"
    assert patch.header.version == "1.40"
    assert patch.header.name == "NYC Muff"
    assert patch.header.group_id == 3
    assert patch.header.effect_id == 0x030000D0
    
    # Check for known blocks
    tags = [b.tag for b in patch.blocks]
    assert "ICON" in tags
    assert "TXE1" in tags
    assert "PRMJ" in tags or "PRME" in tags

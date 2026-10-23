import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import make_controller_fw as ctl  # noqa: E402

STOCK = ROOT / "build/fw/res1_493412.bin"


def test_stock_word_is_230():
    assert ctl.gate_value(ctl.GATE_SITE[2]) == 230.0


def test_340_changes_only_the_constant():
    w = ctl.gate_word(340)
    assert ctl.gate_value(w) == 340.0
    assert (w ^ ctl.GATE_SITE[2]) & ~(0xffff << 7) == 0


@pytest.mark.parametrize("bad", [229.0, 401.0, 340.5])
def test_refused(bad):
    with pytest.raises(ValueError):
        ctl.gate_word(bad)


@pytest.mark.skipif(not STOCK.exists(), reason="stock firmware not present")
def test_site_holds_stock_word():
    d = STOCK.read_bytes()
    vma, off, word = ctl.GATE_SITE
    assert struct.unpack_from("<I", d, off)[0] == word
    assert off + 0xc010c084 == vma

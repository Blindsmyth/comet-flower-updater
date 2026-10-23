"""ONE-TIME boot-logo installer (tools/make_boot_logo_updater.py): only the 184 logo bytes may change."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import make_boot_logo_updater as b  # noqa: E402
import make_fs_restore_updater as upd  # noqa: E402

STOCK = ROOT / "build/fw/res5_163840.bin"
pytestmark = pytest.mark.skipif(not STOCK.exists(), reason="stock boot program not present")


def test_flower_changes_only_the_logo():
    stock = STOCK.read_bytes()
    out = b.new_boot(stock, upd.splash_bytes(str(ROOT / "assets/boot_logo_flower.png"), 92, 16))
    diff = [i for i in range(len(stock)) if out[i] != stock[i]]
    assert diff and b.LOGO_OFF <= diff[0] and diff[-1] < b.LOGO_OFF + b.LOGO_LEN
    assert b.ais_walk(out) == b.ais_walk(stock)


def test_same_logo_is_identity():
    stock = STOCK.read_bytes()
    assert b.new_boot(stock, upd.ZOOM_LOGO) == stock


def test_refuses_non_stock_boot():
    stock = bytearray(STOCK.read_bytes())
    stock[0x100] ^= 1
    with pytest.raises(ValueError):
        b.new_boot(bytes(stock), upd.ZOOM_LOGO)


def test_refuses_wrong_logo_size():
    with pytest.raises(ValueError):
        b.new_boot(STOCK.read_bytes(), bytes(100))


def test_stages_are_zooms_own():
    assert b.STAGES == [upd.EXPECTED[3], upd.EXPECTED[4]]

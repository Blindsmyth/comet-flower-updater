import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import make_splash  # noqa: E402
import make_fs_restore_updater as upd  # noqa: E402


def test_splash_is_128x32_and_encodes(tmp_path):
    p = tmp_path / "s.png"
    make_splash.make("0.34.2").save(p)
    data = upd.splash_bytes(str(p))
    assert len(data) == 512 and any(data)


def test_bottom_line_clear_of_title():
    im = make_splash.make("0.34.2").convert("L")
    rows = [y for y in range(32) if any(im.getpixel((x, y)) for x in range(128))]
    assert rows[0] >= 1 and rows[-1] <= 28 and not any(im.getpixel((x, 16)) for x in range(128))


def test_too_wide_refused():
    with pytest.raises(SystemExit):
        make_splash.make("0.34.2", title="COMET FLOWER")

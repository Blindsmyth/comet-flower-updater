import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ceiling_test as ct  # noqa: E402


class FakeLink:
    def __init__(self, seqs, peak=66177):
        self.seqs, self.peak = list(seqs), peak

    def peek(self, addr, n):
        assert (addr, n) == (ct.CPU_ADDR, ct.CPU_LEN)
        if not self.seqs:
            raise ct.NoReply("gone")
        return struct.pack("<9I", ct.MAGIC, self.seqs.pop(0), 13235, self.peak, 23400, 0, 0, 0, 0)


def test_reading_matches_meter_percent():
    r = ct.read_cpu(FakeLink([1]))
    assert r["peak"] == pytest.approx(50.0, abs=0.01) and r["slots"][0] == pytest.approx(23.4)


def test_stall_after_three_repeats():
    m = ct.Monitor(FakeLink([1, 2, 2, 2, 2]))
    assert [m.sample(show=False) for _ in range(5)] == ["ok", "ok", "ok", "ok", "stall"]


def test_no_reply_raises():
    m = ct.Monitor(FakeLink([1]))
    m.sample(show=False)
    with pytest.raises(ct.NoReply):
        m.sample(show=False)

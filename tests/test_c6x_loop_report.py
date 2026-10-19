"""Software-pipeline report parsing (tools/c6x_loop_report.py), offline."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import c6x_loop_report as lr  # noqa: E402

# Shortened from cl6x 8.5.0 -mw output of CF Muff (muff_g1.h:229) and its copy loop.
LISTING = r""";*----------------------------------------------------------------------------*
;*  SOFTWARE PIPELINE INFORMATION
;*    Loop found in file               : ../muffx.c
;*    Loop inlined from                : ..\muff_g1.h
;*    Loop source line                 : 229
;*
;*    Known Minimum Iteration Count    : 4
;*    Known Maximum Iteration Count    : 4
;*    Loop Carried Dependency Bound(^) : 116
;*    Unpartitioned Resource Bound     : 31
;*    Partitioned Resource Bound(*)    : 37
;*
;*    Searching for software pipeline schedule at ...
;*      ii = 116 Did not find schedule
;*      ii = 123 Did not find schedule
;*    Disqualified loop: Did not find schedule
;*----------------------------------------------------------------------------*
$C$L4:
           MVK     .S1     33,A5
;*----------------------------------------------------------------------------*
;*  SOFTWARE PIPELINE INFORMATION
;*    Loop found in file               : ../muffx.c
;*    Loop source line                 : 47
;*    Loop Unroll Multiple             : 2x
;*    Known Minimum Iteration Count    : 8
;*    Known Maximum Iteration Count    : 8
;*    Loop Carried Dependency Bound(^) : 1
;*    Partitioned Resource Bound(*)    : 2
;*    Searching for software pipeline schedule at ...
;*      ii = 2  Schedule found with 2 iterations in parallel
;*    Total cycles (est.)         : 2 + min_trip_cnt * 2 = 18
;*----------------------------------------------------------------------------*
;*  SOFTWARE PIPELINE INFORMATION
;*    Loop found in file               : ../dynacx.c
;*    Loop source line                 : 57
;*    Disqualified loop: Loop contains control code
;*----------------------------------------------------------------------------*
"""


class LoopReport(unittest.TestCase):
    def setUp(self):
        self.loops = lr.parse(LISTING)

    def test_blocks(self):
        self.assertEqual(len(self.loops), 3)

    def test_feedback_bound_loop_not_pipelined(self):
        lp = self.loops[0]
        self.assertEqual((lp["line"], lp["dep"], lp["res"], lp["trip_min"]), ("229", 116, 37, 4))
        self.assertNotIn("ii", lp)
        self.assertEqual(lp["disq"], "Did not find schedule")
        self.assertEqual(lr.limiter(lp), "feedback (116 vs 37)")

    def test_pipelined_loop(self):
        lp = self.loops[1]
        self.assertEqual((lp["ii"], lp["par"], lp["unroll"]), (2, 2, "2x"))
        self.assertEqual(lr.limiter(lp), "units")

    def test_control_code_loop(self):
        lp = self.loops[2]
        self.assertEqual(lp["disq"], "Loop contains control code")
        self.assertEqual(lr.limiter(lp), "")

    def test_table(self):
        md = "\n".join(lr.table(self.loops, "MUFFX"))
        self.assertIn("| muff_g1.h:229 | 4 | 116 | 37 | - |", md)
        self.assertIn("3 loops, 2 not pipelined.", md)


if __name__ == "__main__":
    unittest.main()

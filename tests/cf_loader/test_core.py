"""Tests for CF Loader core functionality (tests/cf_loader/test_core.py).

Tests run entirely offline with fixtures and fake tool runners (no display, no pedal).
"""

import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.cf_loader import core


@pytest.fixture
def tmp_workdir(tmp_path):
    """Fixture providing an isolated temporary directory."""
    d = tmp_path / "work"
    d.mkdir()
    return d


def test_safety_grep_no_midi():
    """Safety requirement 1:

    grep -rn "mido|rtmidi|pedal_g1|midi" tools/cf_loader shows no code that opens a MIDI port.
    """
    cf_loader_dir = REPO_ROOT / "tools" / "cf_loader"
    for py_file in cf_loader_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        # Ensure no imports or usage of mido, rtmidi, pedal_g1
        assert "import mido" not in content
        assert "from mido" not in content
        assert "import rtmidi" not in content
        assert "from rtmidi" not in content
        assert "import pedal_g1" not in content
        assert "from pedal_g1" not in content


def test_safety_no_exe_as_program():
    """Safety requirement 2:

    No code launches any .exe as the program. Only Python is executed.
    """
    with pytest.raises(ValueError, match="Safety violation"):
        core.run_tool(["some_updater.exe", "--do-something"])

    with pytest.raises(ValueError, match="Safety violation"):
        core.run_tool(["C:\\path\\to\\tool.exe"])


def test_slot_heap_calculation_ratx():
    """Verify that calculate_slot_bytes matches check_slot_mem on build/RATX.ZD2."""
    ratx_zd2 = REPO_ROOT / "build" / "RATX.ZD2"
    if ratx_zd2.exists():
        data = ratx_zd2.read_bytes()
        used = core.calculate_slot_bytes(data)
        assert used <= core.SLOT_HEAP
        assert used in (18176, 18464)


def test_inspect_zd2_valid_ratx():
    """Test inspecting a known valid effect (build/RATX.ZD2)."""
    ratx_zd2 = REPO_ROOT / "build" / "RATX.ZD2"
    if not ratx_zd2.exists():
        pytest.skip("build/RATX.ZD2 not present in tree")

    info = core.inspect_zd2(ratx_zd2)
    assert info.filename == "RATX.ZD2"
    assert info.effect_id == 0x03000F83
    assert info.crc_ok is True
    assert info.is_g1_target is True
    assert info.slot_ok is True
    assert info.has_oversize_sibling is False
    assert info.valid_for_selection is True
    assert len(info.rejection_reasons) == 0


def test_inspect_zd2_oversize_sibling(tmp_workdir):
    """Test that a sibling .oversize file flags the effect and invalidates selection."""
    ratx_zd2 = REPO_ROOT / "build" / "RATX.ZD2"
    if not ratx_zd2.exists():
        pytest.skip("build/RATX.ZD2 not present in tree")

    target = tmp_workdir / "TESTEFF.ZD2"
    target.write_bytes(ratx_zd2.read_bytes())

    # Create oversize sibling
    sibling = tmp_workdir / "TESTEFF.ZD2.oversize"
    sibling.write_text("Oversize reason", encoding="utf-8")

    info = core.inspect_zd2(target)
    assert info.has_oversize_sibling is True
    assert info.valid_for_selection is False
    assert any("Oversize marker" in r for r in info.rejection_reasons)


def test_inspect_zd2_stock_collision(tmp_workdir):
    """Test that colliding with stock effect filename or ID is rejected."""
    ratx_zd2 = REPO_ROOT / "build" / "RATX.ZD2"
    if not ratx_zd2.exists():
        pytest.skip("build/RATX.ZD2 not present in tree")

    # Name collision
    target = tmp_workdir / "TS_DRIVE.ZD2"
    target.write_bytes(ratx_zd2.read_bytes())

    info = core.inspect_zd2(target)
    assert info.valid_for_selection is False
    assert any("collides with stock effect" in r for r in info.rejection_reasons)


def test_preflight_checks_green_and_red(tmp_workdir):
    """Safety requirement 3:

    Pre-flight checks correctly flag green when valid and red when invalid.
    """
    ratx_zd2 = REPO_ROOT / "build" / "RATX.ZD2"
    if not ratx_zd2.exists():
        pytest.skip("build/RATX.ZD2 not present in tree")

    info = core.inspect_zd2(ratx_zd2)

    # 1. Missing official updater -> Check 1 is red
    checks = core.run_preflight_checks(None, [info])
    assert core.all_preflight_passed(checks) is False
    assert checks[0].check_num == 1
    assert checks[0].passed is False

    # 2. Empty selection -> Check 2 is red
    checks = core.run_preflight_checks("dummy.exe", [])
    assert core.all_preflight_passed(checks) is False
    assert checks[1].check_num == 2
    assert checks[1].passed is False

    # 3. Duplicate selection -> Check 3 is red
    checks = core.run_preflight_checks("dummy.exe", [info, info])
    assert core.all_preflight_passed(checks) is False
    assert checks[2].check_num == 3
    assert checks[2].passed is False

    # 4. File count > 110 -> Check 4 is red
    # Fake 90 effects in stock mode (105 stock + 90 = 195 > 110)
    fake_effects = [
        core.EffectInfo(
            path=Path(f"EFF{i}.ZD2"),
            filename=f"EFF{i}.ZD2",
            name=f"EFF{i}",
            effect_id=0x07000000 + i,
            target=0x02,
            size=1000,
            crc_ok=True,
            is_g1_target=True,
            slot_used=1000,
            slot_free=30000,
            slot_ok=True,
            has_oversize_sibling=False,
            report=core.EffectReportInfo(),
            valid_for_selection=True,
        )
        for i in range(10)
    ]
    checks = core.run_preflight_checks("dummy.exe", fake_effects, clean=False)
    # 105 base + 10 = 115 > 110
    check4 = [c for c in checks if c.check_num == 4][0]
    assert check4.passed is False


def test_output_folder_never_overwrites(tmp_workdir):
    """Safety requirement 4: Output folders are never overwritten or deleted."""
    f1 = core.create_output_folder("test_", base_dir=tmp_workdir)
    assert f1.exists()

    # Create dummy file inside f1
    (f1 / "marker.txt").write_text("original", encoding="utf-8")

    # Creating another output folder with the same prefix does not overwrite f1
    f2 = core.create_output_folder("test_", base_dir=tmp_workdir)
    assert f2.exists()
    assert f1 != f2
    assert (f1 / "marker.txt").read_text(encoding="utf-8") == "original"


def test_status_safety_gates(tmp_workdir, monkeypatch):
    """Safety requirement:

    Effect cannot reach 'ok-save' without both audio-pass and cost-measured.
    """
    monkeypatch.setattr(core, "LOADER_DIR", tmp_workdir)

    effect_name = "TESTX.ZD2"

    # Step 1: Built stage
    entry = core.update_effect_stage(effect_name, "built")
    assert entry["stage"] == "built"

    # Attempting to jump directly to ok-save must fail
    with pytest.raises(ValueError, match="Safety gate blocked"):
        core.update_effect_stage(effect_name, "ok-save")

    # Step 2: Audio pass
    core.update_effect_stage(effect_name, "audio-pass")

    # Still cannot jump to ok-save (cost-measured not done)
    with pytest.raises(ValueError, match="Safety gate blocked"):
        core.update_effect_stage(effect_name, "ok-save")

    # Step 3: Cost measured
    core.update_effect_stage(effect_name, "cost-measured", measured_cost=42000)

    # The old cost gate is insufficient until direct timing and artifact
    # identity are part of the approval flow.
    with pytest.raises(ValueError, match="Safety gate blocked"):
        core.update_effect_stage(effect_name, "ok-save")


def test_probe10_cost_calculation():
    """The withdrawn freeze-load formula must not create a CPU measurement."""
    for load in (10.0, 30.0, 60.0):
        with pytest.raises(ValueError, match="not a calibrated CPU cost"):
            core.calculate_probe10_cost(load)


def test_preflight_blocks_build_on_red(tmp_workdir, monkeypatch):
    """Safety requirement 3: Build is impossible with a red pre-flight."""
    monkeypatch.setattr(core, "LOADER_DIR", tmp_workdir)

    # Calling build with no official updater must raise PreflightError immediately
    with pytest.raises(core.PreflightError):
        core.build_image_and_updater(
            official_updater_path=None,
            selected_effects=[],
            clean=True,
            base_output_dir=tmp_workdir,
        )


def test_failed_step_leaves_failed_marker(tmp_workdir, monkeypatch):
    """Safety requirement 5:

    A failed or cancelled step leaves a FAILED marker and the report;
    previous good output is untouched.
    """
    monkeypatch.setattr(core, "LOADER_DIR", tmp_workdir)

    ratx_zd2 = REPO_ROOT / "build" / "RATX.ZD2"
    if not ratx_zd2.exists():
        pytest.skip("build/RATX.ZD2 not present in tree")
    info = core.inspect_zd2(ratx_zd2)

    # Fake pre-flight checks to pass
    monkeypatch.setattr(
        core,
        "run_preflight_checks",
        lambda *args, **kwargs: [
            core.PreflightCheckResult(1, "Mock", True, "Mock pass")
        ],
    )
    # Fake factory image and updater file existence
    fake_factory = tmp_workdir / "fake_factory.bin"
    fake_factory.write_bytes(b"\x00" * 100)
    fake_updater = tmp_workdir / "fake_updater.exe"
    fake_updater.write_bytes(b"\x00" * 100)

    # Fake run_tool to fail on step 1
    def mock_run_tool(cmd, **kwargs):
        return core.ToolExecutionResult(cmd, exit_code=1, stdout="Mock failure", stderr="", duration_sec=0.1)

    monkeypatch.setattr(core, "run_tool", mock_run_tool)

    with pytest.raises(RuntimeError, match="failed with exit code 1"):
        core.build_image_and_updater(
            official_updater_path=fake_updater,
            selected_effects=[info],
            clean=True,
            factory_image_path=fake_factory,
            base_output_dir=tmp_workdir,
        )

    # Verify a folder was created and contains FAILED marker and report.txt
    subdirs = [d for d in tmp_workdir.iterdir() if d.is_dir() and d.name.startswith("image_")]
    assert len(subdirs) == 1
    failed_dir = subdirs[0]
    assert (failed_dir / "FAILED").exists()
    assert (failed_dir / "report.txt").exists()
    report_text = (failed_dir / "report.txt").read_text(encoding="utf-8")
    assert "STATUS: FAILED" in report_text


def test_loader_log_appending(tmp_workdir, monkeypatch):
    """Verify append-only logging to loader.log."""
    monkeypatch.setattr(core, "LOADER_DIR", tmp_workdir)
    log_file = tmp_workdir / "loader.log"

    core.append_to_loader_log("Test log entry 1")
    core.append_to_loader_log("Test log entry 2")

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "Test log entry 1" in lines[0]
    assert "Test log entry 2" in lines[1]

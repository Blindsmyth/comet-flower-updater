"""Unit tests for Comet Flower Installer core business logic."""

import json
from pathlib import Path
import struct
import tempfile
import pytest

from tools.cf_loader import core

REPO_ROOT = core.REPO_ROOT


def test_version_bump_from_builds_md(tmp_path):
    """Test version auto-detection from markdown table."""
    md = tmp_path / "BUILDS.md"

    # Case 1: Standard table
    md.write_text(
        "| Version | Updater | SHA-256 |\n"
        "|---|---|---|\n"
        "| 0.34.3 | 34c | 12345678 |\n"
        "| 0.34.4 | 34d | 87654321 |\n",
        encoding="utf-8",
    )
    assert core.parse_next_version(md) == "0.34.5"

    # Case 2: Custom version jump
    md.write_text(
        "| Version | Updater |\n"
        "| 0.35.9 | 35 |\n",
        encoding="utf-8",
    )
    assert core.parse_next_version(md) == "0.35.10"

    # Case 3: Missing file fallback
    assert core.parse_next_version(tmp_path / "nonexistent.md") == "0.34.5"


def test_build_make_g1_image_cmd_exact_argv(tmp_path):
    """Assert exact argv for tools/make_g1_image.py."""
    factory = tmp_path / "factory.bin"
    out_img = tmp_path / "out.bin"
    py = tmp_path / "python.exe"
    cf1 = tmp_path / "CF_RAT.ZD2"
    cf2 = tmp_path / "CF_DELAY.ZD2"

    cmd = core.build_make_g1_image_cmd(
        factory_img=factory,
        out_img=out_img,
        keep_stock=["COMP.ZD2", "TS_DRIVE.ZD2"],
        cf_effect_paths=[cf1, cf2],
        clean=True,
        python_exe=py,
    )

    expected = [
        str(py),
        str(REPO_ROOT / "tools" / "make_g1_image.py"),
        "--clean",
        "--keep",
        "COMP.ZD2",
        "--keep",
        "TS_DRIVE.ZD2",
        str(factory),
        str(out_img),
        str(cf1),
        str(cf2),
    ]
    assert cmd == expected


def test_build_make_splash_cmd_exact_argv(tmp_path):
    """Assert exact argv for tools/make_splash.py."""
    out_png = tmp_path / "splash.png"
    py = tmp_path / "python.exe"

    cmd = core.build_make_splash_cmd(
        version="0.34.5",
        out_png=out_png,
        title="CF-ZGX4",
        tag="TEST",
        python_exe=py,
    )

    expected = [
        str(py),
        str(REPO_ROOT / "tools" / "make_splash.py"),
        "0.34.5",
        str(out_png),
        "--title",
        "CF-ZGX4",
        "--tag",
        "TEST",
    ]
    assert cmd == expected


def test_build_make_fs_restore_updater_cmd_exact_argv(tmp_path):
    """Assert exact argv for tools/make_fs_restore_updater.py."""
    official = tmp_path / "official.exe"
    out_exe = tmp_path / "custom.exe"
    fw = tmp_path / "fw.bin"
    fs = tmp_path / "fs.bin"
    presets = tmp_path / "presets.bin"
    splash = tmp_path / "splash.png"
    py = tmp_path / "python.exe"

    cmd = core.build_make_fs_restore_updater_cmd(
        official_updater=official,
        out_exe=out_exe,
        test_controller_fw=fw,
        fs_image=fs,
        presets_bin=presets,
        splash_png=splash,
        python_exe=py,
    )

    expected = [
        str(py),
        str(REPO_ROOT / "tools" / "make_fs_restore_updater.py"),
        str(official),
        str(out_exe),
        "--test-controller-fw",
        str(fw),
        "--image",
        str(fs),
        "--presets",
        str(presets),
        "--splash",
        str(splash),
    ]
    assert cmd == expected


def test_backup_scanning_and_deletion(tmp_path):
    """Test discovering backups and computing metrics."""
    backups_root = tmp_path / "backups"
    backups_root.mkdir()

    # Create mock backup 1
    b1 = backups_root / "2026-10-20_120000"
    (b1 / "files").mkdir(parents=True)
    (b1 / "patches").mkdir(parents=True)
    (b1 / "files" / "RATX.ZD2").write_bytes(b"ZDLF" + b"\x00" * 2000)
    (b1 / "files" / "COMP.ZD2").write_bytes(b"ZDLF" + b"\x00" * 3000)
    (b1 / "patches" / "PATCH_001.ZPTC").write_bytes(b"PTCF" + b"\x00" * 756)
    (b1 / "patches" / "PATCH_002.ZPTC").write_bytes(b"PTCF" + b"\x00" * 756)
    (b1 / "backup_manifest.json").write_text("{}", encoding="utf-8")

    # Scan
    found = core.scan_backups(search_dirs=[backups_root])
    assert len(found) == 1
    info = found[0]
    assert info.effects_count == 2
    assert info.patches_count == 2
    assert info.manifest_present is True
    assert info.size_bytes > 5000

    # Delete
    assert core.delete_backup(b1) is True
    assert not b1.exists()
    assert len(core.scan_backups(search_dirs=[backups_root])) == 0


def test_patch_decoding_from_fake_folder(tmp_path):
    """Test decoding 50 patches from a folder."""
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()

    # Build a synthetic valid patch file
    patch_bytes = bytearray(760)
    patch_bytes[:4] = b"PTCF"
    struct.pack_into("<I", patch_bytes, 4, 760)
    struct.pack_into("<I", patch_bytes, 8, 1)   # version
    struct.pack_into("<I", patch_bytes, 12, 5)  # 5 slots
    # Name at 26
    patch_bytes[26:36] = b"Lead Solos"
    # Tag EDTB at 100
    patch_bytes[100:104] = b"EDTB"
    struct.pack_into("<I", patch_bytes, 104, 120)

    (patches_dir / "PATCH_001.ZPTC").write_bytes(patch_bytes)

    patches = core.scan_backup_patches(backup_dir=tmp_path)
    assert len(patches) == 50
    assert patches[0].index == 1
    assert patches[0].name == "Lead Solos"
    # Slots 2..50 should default to empty
    assert patches[1].is_empty is True
    assert patches[1].name == "Patch 02"


def test_profile_crud_and_default(tmp_path):
    """Test profile save, load, rename, delete, and default selection."""
    prof_file = tmp_path / "profiles.json"

    p1 = core.Profile(
        name="Stage 1",
        is_default=True,
        checked_effects=["RATX.ZD2", "DELAYX.ZD2"],
        firmware_path="/path/to/fw.bin",
        version="0.34.5",
        backup_before_build=True,
    )
    p2 = core.Profile(
        name="Stage 2",
        is_default=False,
        checked_effects=["COMP.ZD2"],
        firmware_path="/path/to/fw2.bin",
        version="0.34.6",
        backup_before_build=False,
    )

    core.save_profile(p1, prof_file)
    core.save_profile(p2, prof_file)

    loaded = core.load_profiles(prof_file)
    assert len(loaded) == 2
    assert loaded["Stage 1"].is_default is True
    assert loaded["Stage 2"].is_default is False

    # Switch default
    core.set_default_profile("Stage 2", prof_file)
    assert core.get_default_profile(prof_file).name == "Stage 2"

    # Rename
    assert core.rename_profile("Stage 1", "Studio 1", prof_file) is True
    loaded_after_rename = core.load_profiles(prof_file)
    assert "Studio 1" in loaded_after_rename
    assert "Stage 1" not in loaded_after_rename

    # Delete
    assert core.delete_profile("Studio 1", prof_file) is True
    final_profs = core.load_profiles(prof_file)
    assert len(final_profs) == 1
    assert "Stage 2" in final_profs


def test_filesystem_sizing_limits():
    """Test filesystem space and blocks verification."""
    # Under limit
    fx_small = [
        core.UnifiedEffect(
            filename=f"FX_{i}.ZD2",
            name=f"FX {i}",
            group="DRV",
            group_id=3,
            source="CF",
            dspload=20.0,
            size_bytes=25000,
            effect_id=0x07000000 + i,
        )
        for i in range(10)
    ]
    total_bytes, total_blocks, free_blocks, fits, msg = core.calculate_filesystem_usage(fx_small)
    assert fits is True
    assert free_blocks > 0

    # Over limit (too many entries / massive files)
    fx_huge = [
        core.UnifiedEffect(
            filename=f"HUGE_{i}.ZD2",
            name=f"Huge {i}",
            group="DRV",
            group_id=3,
            source="CF",
            dspload=20.0,
            size_bytes=200000,
            effect_id=0x07000000 + i,
        )
        for i in range(20)
    ]
    tot_bytes_h, tot_blocks_h, free_blocks_h, fits_h, msg_h = core.calculate_filesystem_usage(fx_huge)
    assert fits_h is False
    assert "Size exceeded" in msg_h or "Blocks exceeded" in msg_h



def test_theme_tint_and_scale_image():
    """Verify that tint_and_scale_image produces a valid tinted Image."""
    from tools.cf_loader.theme import tint_and_scale_image
    logo_path = REPO_ROOT / "assets" / "logo_comet_flower.png"
    if logo_path.exists():
        img = tint_and_scale_image(logo_path, gold_rgb=(212, 175, 55), scale=2)
        assert img.size == (184, 32)
        # Sample lit pixel should have gold color (212, 175, 55)
        has_gold = any(
            img.getpixel((x, y))[:3] == (212, 175, 55)
            for x in range(img.width)
            for y in range(img.height)
        )
        assert has_gold is True


def test_make_blank_patch():
    """Verify synthetic blank patch creation."""
    patch_data = core.make_blank_patch(index=5, name="CleanTone")
    assert len(patch_data) == 760
    assert patch_data[:4] == b"PTCF"
    assert b"CleanTone" in patch_data[26:36]


def test_installer_build_pipeline_mocked(tmp_path, monkeypatch):
    """Test full execute_cf_installer_build with mocked subprocess execution."""
    monkeypatch.setattr(core, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(core, "LOADER_DIR", tmp_path / "loader_out")

    upd = tmp_path / "official.exe"
    upd.write_bytes(b"PE_UPDATER_FIXTURE")
    factory = tmp_path / "factory.bin"
    factory.write_bytes(b"FACTORY_FS_FIXTURE")
    fw = tmp_path / "fw.bin"
    fw.write_bytes(b"FIRMWARE_BIN_FIXTURE")

    # Mock verify_official_updater
    monkeypatch.setattr(
        core,
        "verify_official_updater",
        lambda p: core.UpdaterVerification(True, Path(p), 18, "ABCD", "Mock valid"),
    )

    # Mock stock catalog to return fake stock effects
    fake_stock = {
        "COMP.ZD2": core.UnifiedEffect("COMP.ZD2", "Comp", "DYN", 1, "Zoom", 20.0, 20000, 0x01000010),
        "TS_DRIVE.ZD2": core.UnifiedEffect("TS_DRIVE.ZD2", "TS Drive", "DRV", 3, "Zoom", 25.0, 22000, 0x03000010),
    }
    monkeypatch.setattr(core, "load_stock_catalog", lambda *_: fake_stock)

    calls = []
    def fake_run_tool(cmd, **kwargs):
        calls.append(cmd)
        cmd_str = " ".join(cmd)
        # Mock file creation for steps that would normally generate output
        for arg in cmd:
            if arg.endswith(".bin") or arg.endswith(".png") or arg.endswith(".exe"):
                p = Path(arg)
                if not p.exists() and "tools" not in str(p):
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(b"GENERATED_BINARY_OUTPUT")
        if "check_updater_stages.py" in cmd_str:
            return core.ToolExecutionResult(cmd, 0, "erase 0x102000 size 0x2fe000 ok\nwrite 0x102000 resource 0x88 ok", "", 0.01)
        elif "make_fs_restore_updater.py" in cmd_str:
            return core.ToolExecutionResult(
                cmd,
                0,
                "stages:\n   erase 0x00028000 size 0xb000\n   write 0x00028000 resource 0x85\n   erase 0x00102000 size 0x2fe000\n   write 0x00102000 resource 0x88\n",
                "",
                0.01,
            )
        return core.ToolExecutionResult(cmd, 0, "mock ok", "", 0.01)

    monkeypatch.setattr(core, "run_tool", fake_run_tool)

    log_dest = tmp_path / "installer_log.json"
    monkeypatch.setattr(core, "INSTALLER_LOG_PATH", log_dest)

    # Execute build
    result = core.execute_cf_installer_build(
        official_updater_path=upd,
        firmware_bin_path=fw,
        selected_stock_effects=["COMP.ZD2"],
        selected_cf_effects=[],
        version="0.34.5",
        presets_bin_path=None,
        patch_records=None,
        do_backup=False,
        factory_image_path=factory,
        base_output_dir=tmp_path / "builds",
    )

    assert result["version"] == "0.34.5"
    assert "exe_path" in result
    assert Path(result["exe_path"]).exists()
    assert len(result["stages"]) >= 2

    # Check installer_log.json was written
    assert log_dest.exists()
    records = json.loads(log_dest.read_text(encoding="utf-8"))
    assert len(records) == 1
    assert records[0]["version"] == "0.34.5"
    assert records[0]["sha256"] == result["sha256"]


def test_write_patch_live_refuses_bad_input():
    import pytest
    from tools.cf_loader import patches
    with pytest.raises(RuntimeError):
        patches.write_patch_live(0, b"PTCF" + bytes(756))
    with pytest.raises(RuntimeError):
        patches.write_patch_live(5, b"XXXX" + bytes(756))


def test_write_patch_live_reports_no_pedal(monkeypatch):
    import pytest
    import sys
    from tools.cf_loader import patches
    sys.path.insert(0, str(patches.REPO_ROOT / "tools"))
    import ua_bench

    def no_port():
        sys.exit("FAIL: no port")
    monkeypatch.setattr(ua_bench, "pedal_session", no_port)
    with pytest.raises(RuntimeError, match="no port"):
        patches.write_patch_live(5, b"PTCF" + bytes(756))


def test_firmware_default_is_a_finished_res1(tmp_path, monkeypatch):
    from tools.cf_loader import build_engine
    d = tmp_path / "build" / "cf_header"
    d.mkdir(parents=True)
    (d / "res1_a.bin").write_bytes(bytes(200000))
    (d / "ctl_b.bin").write_bytes(bytes(200000))       # newer, but intermediate
    monkeypatch.setattr(build_engine, "REPO_ROOT", tmp_path)
    assert build_engine.find_default_firmware_bin().name == "res1_a.bin"


def test_default_firmware_is_the_flash_this_row(tmp_path, monkeypatch):
    import hashlib
    from tools.cf_loader import build_engine
    d = tmp_path / "build" / "cf_header"
    d.mkdir(parents=True)
    good, shelved = bytes([1]) * 200000, bytes([2]) * 200000
    (d / "res1_good.bin").write_bytes(good)
    (d / "res1_newer_shelved.bin").write_bytes(shelved)       # newest file, not approved
    h = hashlib.sha256(good).hexdigest()[:8]
    md = tmp_path / "BUILDS.md"
    md.write_text("| Version | Updater | SHA-256 | Firmware | FS image | What | Status |\n"
                  "|---|---|---|---|---|---|---|\n"
                  "| 0.1.0 | 1 | aaaaaaaa | %s | fs | x | **flash this** |\n"
                  "| 0.1.1 | 2 | bbbbbbbb | %s | fs | y | not wanted |\n"
                  % (h, hashlib.sha256(shelved).hexdigest()[:8]), encoding="utf-8")
    monkeypatch.setattr(build_engine, "REPO_ROOT", tmp_path)
    assert build_engine.find_default_firmware_bin(md).name == "res1_good.bin"

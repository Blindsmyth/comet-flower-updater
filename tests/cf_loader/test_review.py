import time
import pytest
from tools.cf_loader import core

@pytest.mark.parametrize('cancel', [False, True])
def test_silent_child_deadline(tmp_path, monkeypatch, cancel):
    monkeypatch.setattr(core, 'LOADER_DIR', tmp_path)
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        core.run_tool([str(core.get_python_exe()), '-c', 'import time; time.sleep(1.5)'],
                      timeout=5 if cancel else .15,
                      is_cancelled=(lambda: time.monotonic() - start > .15) if cancel else None)
    assert time.monotonic() - start < 1.2
from pathlib import Path
import struct
import zlib


def effect_file(path, effect_id=0x03000F83, target=2, memsz=1000):
    """Small synthetic ZD2 with one ELF load segment and section-name table."""
    elf = bytearray(200)
    elf[:4] = b'\x7fELF'
    struct.pack_into('<II', elf, 0x1c, 52, 84)
    struct.pack_into('<HHHHH', elf, 0x2a, 32, 1, 40, 1, 0)
    struct.pack_into('<6I', elf, 52, 1, 0, 0, 0, 0, memsz)
    struct.pack_into('<10I', elf, 84, 0, 0, 0, 0, 124, 1, 0, 0, 0, 0)
    data = bytearray(128) + elf + bytearray(16)
    data[:4] = b'ZDLF'
    struct.pack_into('<I', data, 12, target)
    struct.pack_into('<I', data, 0x60, effect_id)
    struct.pack_into('<I', data, 8, zlib.crc32(data[12:-16]) ^ 0xffffffff)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return core.inspect_zd2(path)


@pytest.fixture
def build_env(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'REPO_ROOT', tmp_path)
    monkeypatch.setattr(core, 'LOADER_DIR', tmp_path / 'outputs')
    updater = tmp_path / 'official.exe'
    updater.write_bytes(b'fixture')
    factory = tmp_path / 'factory.bin'
    factory.write_bytes(b'fixture')
    monkeypatch.setattr(core, 'verify_official_updater', lambda p:
        core.UpdaterVerification(True, Path(p), 7, '1234', 'fixture verified'))
    effect = effect_file(tmp_path / 'build' / 'CUSTOM.ZD2')
    calls = []
    def runner(cmd, **kwargs):
        calls.append(cmd)
        return core.ToolExecutionResult(cmd, 0, 'erase 0x102000 size 0x2fe000 ok\nwrite 0x102000 resource 0x88 ok', '', .01)
    monkeypatch.setattr(core, 'run_tool', runner)
    return dict(official_updater_path=updater, selected_effects=[effect], factory_image_path=factory), calls


@pytest.mark.parametrize('defect', ['missing', 'target', 'crc', 'slot', 'id', 'name', 'stock_id', 'oversize', 'count'])
def test_probe_preflight_blocks(defect, build_env, tmp_path):
    args, calls = build_env
    probe = tmp_path / 'build' / 'PROBE10.ZD2'
    if defect != 'missing':
        effect_file(probe, effect_id=0x07000f90, target=1 if defect == 'target' else 2,
                    memsz=50000 if defect == 'slot' else 1000)
    if defect == 'crc':
        data = bytearray(probe.read_bytes()); data[8] ^= 1; probe.write_bytes(data)
    if defect == 'id':
        effect_file(probe)
    if defect == 'stock_id':
        effect_file(probe, effect_id=next(iter(core.STOCK_EFFECT_IDS)))
    if defect == 'oversize':
        probe.with_suffix('.ZD2.oversize').write_text('oversize')
    if defect == 'name':
        args['selected_effects'].append(effect_file(tmp_path / 'elsewhere' / 'PROBE10.ZD2', effect_id=0x07000f91))
    if defect == 'count':
        args['clean'] = False
        args['selected_effects'] += [effect_file(tmp_path / 'build' / f'E{i}.ZD2', effect_id=0x07000fa0+i) for i in range(4)]
    checks = core.run_preflight_checks(args['official_updater_path'], args['selected_effects'],
                                      clean=args.get('clean', True), add_probe10=True)
    assert not core.all_preflight_passed(checks)
    with pytest.raises(core.PreflightError):
        core.build_image_and_updater(**args, add_probe10=True)
    assert calls == []
    assert not core.LOADER_DIR.exists()


def test_probe_once_and_report(build_env, tmp_path):
    args, calls = build_env
    probe = effect_file(tmp_path / 'build' / 'PROBE10.ZD2', effect_id=0x07000f90)
    args['selected_effects'].append(probe)
    out = core.build_image_and_updater(**args, add_probe10=True)
    assert calls[0].count(str(probe.path)) == 1
    assert 'Estimated 29 files' in (out / 'report.txt').read_text()
    assert 'EXEC:' in (out / 'report.txt').read_text()
    assert not (out / 'FAILED').exists()


@pytest.mark.parametrize('recovery', [False, True])
@pytest.mark.parametrize('failure', ['exit', 'cancel', 'no_stages', 'refused'])
def test_pipeline_failure_preserves_outputs(build_env, monkeypatch, recovery, failure):
    args, calls = build_env
    previous = core.create_output_folder('previous_')
    (previous / 'good').write_bytes(b'unchanged')
    def runner(cmd, **kwargs):
        calls.append(cmd)
        if failure == 'cancel':
            raise TimeoutError('cancelled')
        output = {'exit': 'error', 'no_stages': '', 'refused': 'erase 0x0 size 0x28000 REFUSED: boot'}[failure]
        return core.ToolExecutionResult(cmd, 1 if failure == 'exit' else 0, output, '', .01)
    monkeypatch.setattr(core, 'run_tool', runner)
    with pytest.raises((RuntimeError, TimeoutError)):
        if recovery:
            core.build_factory_restore_updater(args['official_updater_path'])
        else:
            core.build_image_and_updater(**args)
    failed = list(core.LOADER_DIR.glob('*/FAILED'))
    assert len(failed) == 1
    assert 'STATUS: FAILED' in failed[0].with_name('report.txt').read_text()
    assert 'EXEC:' in failed[0].with_name('report.txt').read_text()
    assert (previous / 'good').read_bytes() == b'unchanged'
    if recovery:
        assert all('--image' not in cmd for cmd in calls)


def test_recovery_without_library(build_env, monkeypatch):
    args, calls = build_env
    monkeypatch.setattr(core, 'scan_library', lambda: pytest.fail('Recovery must not scan library'))
    out = core.build_factory_restore_updater(args['official_updater_path'])
    assert not (out / 'FAILED').exists()
    assert len(calls) == 2
    assert Path(calls[1][1]).name == 'check_updater_stages.py'
    assert '--image' not in calls[0]


@pytest.mark.parametrize('output', [
    'erase 0x102000 size 0x2fe000 ok',
    'write 0x102000 resource 0x88 ok',
    'erase 0x102000 size 0x2fe000 ok\nwrite 0x102000 resource 0x81 ok',
])
def test_stage_gate_requires_filesystem_pair(output):
    result = core.ToolExecutionResult([], 0, output, '', 0)
    assert not core.stages_verified(result)


@pytest.mark.parametrize('check_num', range(1, 8))
def test_each_red_check_blocks(build_env, monkeypatch, check_num):
    args, calls = build_env
    monkeypatch.setattr(core, 'run_preflight_checks', lambda *a, **kw:
        [core.PreflightCheckResult(i, 'fixture', i != check_num, 'fixture') for i in range(1, 8)])
    with pytest.raises(core.PreflightError):
        core.build_image_and_updater(**args)
    assert not calls


def test_report_setup_failure_marked(build_env, monkeypatch):
    args, _ = build_env
    monkeypatch.setattr(core, 'crc32_of_file', lambda p: (_ for _ in ()).throw(OSError('input disappeared')))
    with pytest.raises(OSError):
        core.build_image_and_updater(**args)
    assert len(list(core.LOADER_DIR.glob('*/FAILED'))) == 1
    assert 'input disappeared' in next(core.LOADER_DIR.glob('*/report.txt')).read_text()


@pytest.mark.parametrize('value', [None, -1, 96001, float('nan'), float('inf')])
def test_cost_requires_valid_measurement(tmp_path, monkeypatch, value):
    monkeypatch.setattr(core, 'LOADER_DIR', tmp_path)
    core.update_effect_stage('X.ZD2', 'audio-pass')
    with pytest.raises(ValueError):
        core.update_effect_stage('X.ZD2', 'cost-measured', measured_cost=value)
    with pytest.raises(ValueError):
        core.update_effect_stage('X.ZD2', 'ok-save')


@pytest.mark.parametrize('value', [-1, 61, float('nan'), float('inf')])
def test_invalid_probe_reading(value):
    with pytest.raises(ValueError):
        core.calculate_probe10_cost(value)


def test_streaming_and_process_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'LOADER_DIR', tmp_path)
    processes = []
    popen = core.subprocess.Popen
    def capture(*a, **kw):
        proc = popen(*a, **kw); processes.append(proc); return proc
    monkeypatch.setattr(core.subprocess, 'Popen', capture)
    lines = []
    res = core.run_tool([str(core.get_python_exe()), '-u', '-c',
                         "import sys; print('first'); sys.stderr.write('last without newline')"], on_output=lines.append)
    assert lines == ['first', 'last without newline']
    assert res.stdout == '\n'.join(lines)
    assert processes[0].poll() == 0 and processes[0].stdout.closed
    with pytest.raises(TimeoutError):
        core.run_tool([str(core.get_python_exe()), '-c', 'import time; time.sleep(10)'], timeout=.1)
    assert processes[1].poll() is not None and processes[1].stdout.closed
    assert (tmp_path / 'loader.log').read_text().count('EXIT:') == 2

def test_rebuild_revokes_old_cost_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'LOADER_DIR', tmp_path)
    core.update_effect_stage('X.ZD2', 'audio-pass')
    core.update_effect_stage('X.ZD2', 'cost-measured', measured_cost=1234)
    with pytest.raises(ValueError, match='Safety gate blocked'):
        core.update_effect_stage('X.ZD2', 'ok-save')
    core.update_effect_stage('X.ZD2', 'in image')
    assert not core.load_status()['X.ZD2']['cost_measured']
    with pytest.raises(ValueError, match='Safety gate blocked'):
        core.update_effect_stage('X.ZD2', 'ok-save')


def test_empty_presets_uses_full_resource(build_env, tmp_path):
    args, calls = build_env
    resource = tmp_path / 'build' / 'fw' / 'res2_45056.bin'
    resource.parent.mkdir(); resource.write_bytes(bytes(0xb000))
    out = core.build_image_and_updater(**args, empty_patches=True)
    blank = next(cmd for cmd in calls if Path(cmd[1]).name == 'g1presets.py')
    patch = next(cmd for cmd in calls if Path(cmd[1]).name == 'make_fs_restore_updater.py')
    assert blank[2:] == ['blank', str(resource), str(out / 'empty_presets.bin')]
    assert patch[patch.index('--presets') + 1] == str(out / 'empty_presets.bin')


def test_changed_effect_revalidated(build_env):
    args, calls = build_env
    args['selected_effects'][0].path.write_bytes(b'changed since library scan')
    with pytest.raises(core.PreflightError):
        core.build_image_and_updater(**args)
    assert not calls


def test_gui_error_callbacks_capture_exception():
    import ast
    tree = ast.parse((Path(core.__file__).with_name('app.py')).read_text())
    for handler in (node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler) and node.name):
        for callback in (node for node in ast.walk(handler) if isinstance(node, ast.Lambda)):
            assert handler.name not in {node.id for node in ast.walk(callback.body) if isinstance(node, ast.Name)}

@pytest.mark.parametrize('missing', [True, False])
def test_probe_build_rejects_missing_or_wrong_target(build_env, tmp_path, missing):
    args, calls = build_env
    if not missing:
        effect_file(tmp_path / 'build' / 'PROBE10.ZD2', effect_id=0x07000f90, target=1)
    with pytest.raises(core.PreflightError):
        core.build_image_and_updater(**args, add_probe10=True)
    assert not calls

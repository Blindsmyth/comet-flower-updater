"""Do not let incomplete stack inventories become finite safety claims."""
from tools.stack_depth import StackInventory, load_evidence, parse_disassembly
import pytest


def inventory(lines, starts, callbacks=None):
    text = '\n'.join(f'{address:08x} 00000000 {line}' for address, line in lines)
    return StackInventory(parse_disassembly(text), [*starts, max(a for a, _ in lines) + 4], callbacks)


def test_scaled_sp_decrements_and_direct_chain():
    walker = inventory([(0x1000, 'STW.D2T2 B3,*B15--[2]'),
                        (0x1004, 'STDW.D2T2 B11:B10,*B15--[1]'),
                        (0x1008, 'CALLP.S2 0x00002000,B3'),
                        (0x2000, 'SUB.L2 B15,0x18,B15'),
                        (0x2004, 'ADDK.S2 -8,B15')], [0x1000, 0x2000])
    report = walker.report(0x1000)
    assert report['accounted_frame_bytes'] == 48
    assert report['stack_bound_bytes'] is None
    assert report['status'] == 'NOT_A_STACK_PROOF'


def test_a3_is_not_implicitly_a_return():
    report = inventory([(0x1000, 'B.S2X A3')], [0x1000]).report(0x1000)
    assert report['functions'][0]['issues'][0]['kind'] == 'INDIRECT'
    assert report['accounted_frame_bytes'] is None


def test_earlier_stack_load_does_not_hide_callback():
    report = inventory([(0x1000, 'LDW.D2T2 *B15[1],B5'),
                        (0x1004, 'LDW.D2T2 *B4[0],B5'),
                        (0x1008, 'B.S2 B5')], [0x1000]).report(0x1000)
    assert report['functions'][0]['issues'][0]['site'] == '0x1008'


def test_callbacks_resolve_only_the_named_site():
    walker = inventory([(0x1000, 'B.S2 B5'), (0x1004, 'B.S2 B7'),
                        (0x2000, 'BNOP.S2 B3,5')], [0x1000, 0x2000],
                       {0x1000: {'source': 'observed slot', 'targets': ['2000']}})
    report = walker.report(0x1000)
    assert report['functions'][0]['edges'] == ['0x2000']
    assert report['functions'][0]['issues'][0]['site'] == '0x1004'
    assert report['accounted_frame_bytes'] is None


def test_cycles_do_not_produce_finite_totals_and_roots_are_independent():
    walker = inventory([(0x1000, 'CALLP.S2 0x00002000,B3'),
                        (0x2000, 'CALLP.S2 0x00001000,B3')], [0x1000, 0x2000])
    first = walker.report(0x1000)
    walker.report(0x2000)
    assert first == walker.report(0x1000)
    assert first['cycles'] == [['0x1000', '0x2000', '0x1000']]
    assert first['accounted_frame_bytes'] is None


def test_live_save_helper_prevents_sibling_frame_subtotal():
    walker = inventory([(0x1000, 'CALLP.S1 0xc016e020,A3'),
                        (0xc016e020, 'STW.D2T2 B14,*B15--[2]')], [0x1000, 0xc016e020])
    report = walker.report(0x1000)
    assert report['functions'][0]['issues'][0]['kind'] == 'LIVE_SAVE_HELPER'
    assert report['accounted_frame_bytes'] is None


def test_missing_target_is_reported():
    report = inventory([(0x1000, 'CALLP.S2 0x00002000,B3')], [0x1000, 0x2000, 0x2100]).report(0x1000)
    assert report['functions'][1]['issues'][0]['kind'] == 'MISSING_INSTRUCTION'
    assert report['accounted_frame_bytes'] is None


def test_empty_observed_ready_hook_set_is_an_assumption():
    report = inventory([(0x1000, 'B.S2X A0')], [0x1000],
                       {0x1000: {'source': 'zero hook fields', 'targets': []}}).report(0x1000)
    assert report['functions'][0]['assumptions']
    assert report['stack_bound_bytes'] is None


def test_callp_through_b3_is_not_a_return():
    report = inventory([(0x1000, 'CALLP.S2 B3,B3')], [0x1000]).report(0x1000)
    assert report['functions'][0]['issues'][0]['kind'] == 'INDIRECT'


def test_uncatalogued_entry_does_not_gain_a_bound():
    report = inventory([(0x1000, 'BNOP.S2 B3,5'),
                        (0x1004, 'BNOP.S2 B3,5')], [0x1000]).report(0x1004)
    assert report['functions'][0]['issues'][0]['kind'] == 'UNCATALOGUED_ENTRY'
    assert report['accounted_frame_bytes'] is None


def test_unknown_entry_does_not_scan_following_code():
    report = inventory([(0x1000, 'CALLP.S2 0x00002000,B3'),
                        (0x2000, 'CALLP.S2 0x00003000,B3'),
                        (0x3000, 'B.S2 B7')], [0x1000, 0x1100]).report(0x1000)
    assert [f['entry'] for f in report['functions']] == ['0x1000', '0x2000']
    assert report['functions'][1]['frame_decrements_bytes'] is None


def test_last_entry_without_extent_does_not_scan_to_image_end():
    walker = StackInventory([(0x1000, 'BNOP.S2 B3,5'), (0x2000, 'B.S2 B7')], [0x1000])
    report = walker.report(0x1000)
    assert report['functions'][0]['issues'][0]['kind'] == 'UNKNOWN_EXTENT'
    assert report['functions'][0]['edges'] == []


def test_cli_report_records_input_hashes_and_unknown_bound(tmp_path, capsys):
    import hashlib
    import json
    from tools.stack_depth import main

    dis = tmp_path / 'main.dis'
    dis.write_text('00001000 00000000 B.S2 B7\n')
    catalog = tmp_path / 'subsystems.tsv'
    catalog.write_text('addr\n1000\n1100\n')
    elf = tmp_path / 'main.elf'
    elf.write_bytes(b'fixture identity; this option hashes without parsing ELF')
    output = tmp_path / 'nested' / 'report.json'
    main(['--dis', str(dis), '--catalog', str(catalog), '--elf', str(elf),
          '--report', str(output), '1000'])
    report = json.loads(output.read_text())
    assert report['inputs']['disassembly']['sha256'] == hashlib.sha256(dis.read_bytes()).hexdigest()
    assert report['inputs']['elf']['sha256'] == hashlib.sha256(elf.read_bytes()).hexdigest()
    assert report['reports'][0]['stack_bound_bytes'] is None
    assert 'NOT_A_STACK_PROOF' in capsys.readouterr().out


def test_callback_observations_from_a_different_image_are_rejected(tmp_path):
    import json
    import pytest
    from tools.stack_depth import main

    dis = tmp_path / 'main.dis'
    dis.write_text('00001000 00000000 B.S2 B7\n')
    callbacks = tmp_path / 'callbacks.json'
    callbacks.write_text(json.dumps({'disassembly_sha256': '0' * 64, 'sites': {}}))
    with pytest.raises(SystemExit) as error:
        main(['--dis', str(dis), '--resolve', '--callbacks', str(callbacks), '1000'])
    assert error.value.code == 2


def test_reviewed_extent_removes_adjacent_function_false_cycle():
    lines = [(0x1000, 'CALLP.S2 0x00002000,B3'),
             (0x2000, 'BNOP.S2 B3,5'),
             (0x2040, 'CALLP.S2 0x00001000,B3')]
    text = '\n'.join(f'{a:08x} 00000000 {line}' for a, line in lines)
    instructions = parse_disassembly(text)
    starts = [0x1000, 0x2000, 0x2100]
    assert StackInventory(instructions, starts).report(0x1000)['cycles']
    extent = {0x2000: {'end': '2020', 'evidence': 'return before separate prologue'}}
    report = StackInventory(instructions, starts, extents=extent).report(0x1000)
    assert not report['cycles']
    assert report['functions'][1]['end'] == '0x2020'
    assert report['stack_bound_bytes'] is None


def test_reviewed_return_applies_only_at_its_instruction():
    lines = [(0x1000, 'B.S2X A3'), (0x1004, 'B.S2X A3')]
    transfers = {0x1000: {'kind': 'return', 'evidence': 'reviewed restored address'}}
    walker = StackInventory(lines, [0x1000, 0x1100], transfers=transfers)
    report = walker.report(0x1000)
    assert report['functions'][0]['issues'][0]['site'] == '0x1004'
    assert report['functions'][0]['assumptions'][0]['site'] == '0x1000'


def test_annotated_stack_switch_remains_a_blocker():
    transfers = {0x1000: {'kind': 'stack_switch', 'evidence': 'selected context return'}}
    walker = StackInventory([(0x1000, 'B.S2 B4')], [0x1000, 0x1100], transfers=transfers)
    report = walker.report(0x1000)
    assert report['functions'][0]['issues'][0]['kind'] == 'STACK_SWITCH'
    assert report['accounted_frame_bytes'] is None


def write_evidence(tmp_path, records):
    import hashlib
    import json

    text = '00001000 00000000 B.S2X A3\n00001004 00000000 NOP 4\n'
    instructions = parse_disassembly(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    path = tmp_path / 'evidence.json'
    path.write_text(json.dumps({'disassembly_sha256': digest, **records}))
    return path, instructions, digest


def test_evidence_checks_instruction_anchors(tmp_path):
    import pytest

    record = {'kind': 'return', 'evidence': 'narrow site',
              'anchors': [{'address': '1000', 'instruction': 'B.S2X A4'}]}
    path, instructions, digest = write_evidence(tmp_path, {'sites': {'1000': record}})
    with pytest.raises(ValueError, match='instruction anchor'):
        load_evidence(path, instructions, digest)


def test_evidence_accepts_whitespace_changes_and_retains_assumptions(tmp_path):
    record = {'kind': 'continuation', 'evidence': 'custom helper return',
              'anchors': [{'address': '1000', 'instruction': 'B.S2X    A3'}]}
    path, instructions, digest = write_evidence(tmp_path, {'sites': {'1000': record}})
    assert load_evidence(path, instructions, digest)['sites']['1000'] == record


def test_evidence_rejects_nonbranch_transfer_site(tmp_path):
    import pytest

    record = {'kind': 'return', 'evidence': 'incorrect location',
              'anchors': [{'address': '1004', 'instruction': 'NOP 4'}]}
    path, instructions, digest = write_evidence(tmp_path, {'sites': {'1004': record}})
    with pytest.raises(ValueError, match='not a register branch'):
        load_evidence(path, instructions, digest)


def test_extent_evidence_rejects_reversed_range(tmp_path):
    import pytest

    record = {'end': 'fff', 'evidence': 'incorrect end',
              'anchors': [{'address': '1000', 'instruction': 'B.S2X A3'}]}
    path, instructions, digest = write_evidence(tmp_path, {'extents': {'1000': record}})
    with pytest.raises(ValueError, match='invalid exclusive end'):
        load_evidence(path, instructions, digest)


def test_evidence_requires_hash_and_anchors(tmp_path):
    import pytest

    record = {'kind': 'return', 'evidence': 'unsupported claim', 'anchors': []}
    path, instructions, digest = write_evidence(tmp_path, {'sites': {'1000': record}})
    with pytest.raises(ValueError, match='SHA-256'):
        load_evidence(path, instructions, 'wrong hash')
    with pytest.raises(ValueError, match='lacks evidence or instruction anchors'):
        load_evidence(path, instructions, digest)


@pytest.mark.parametrize('instruction', [
    'LDW.D2T2 *+B4[0],B15',  # scheduler selects another task stack
    '[!B0] MV.L2 B1,B15',  # interrupt-stack switch, including its predicate
    'AND.L2 -8,B15,B15',  # alignment consumes an unknown amount
    'SUB.L2 B15,B4,B15',  # variable reservation
])
def test_explicit_unknown_sp_writes_block_subtotals(instruction):
    report = inventory([(0x1000, instruction), (0x1004, 'BNOP.S2 B3,5')],
                       [0x1000]).report(0x1000)
    assert report['accounted_frame_bytes'] is None
    assert report['functions'][0]['issues'] == [
        {'kind': 'UNMODELED_SP_WRITE', 'site': '0x1000', 'instruction': instruction}]


@pytest.mark.parametrize('instruction', [
    'ADD.L2 B15,-8,B15', 'ADD.L2 -0x8,B15,B15',
    'ADDK.S2 -0x8,B15', 'SUB.L2 B15,0x8,B15',
])
def test_constant_sp_decrements_include_add_spellings(instruction):
    report = inventory([(0x1000, instruction)], [0x1000]).report(0x1000)
    assert report['accounted_frame_bytes'] == 8


def test_constant_sp_restores_do_not_increase_decrement_inventory():
    report = inventory([(0x1000, 'ADD.L2 8,B15,B15'),
                        (0x1004, 'ADDK.S2 0x8,B15'),
                        (0x1008, 'SUB.L2 B15,-8,B15')], [0x1000]).report(0x1000)
    assert report['accounted_frame_bytes'] == 0
    assert not report['functions'][0]['issues']


def test_reviewed_switch_owner_spans_catalogued_case_fragments():
    lines = [(0x1000, 'SUB.L2 B15,0x8,B15'),
             (0x1004, 'BNOP.S1 0x00001010,5'),
             (0x1008, 'BNOP.S2 B0,5'),
             (0x1010, 'CALLP.S2 0x00002000,B3'),
             (0x1020, 'ADD.L2 8,B15,B15'),
             (0x2000, 'BNOP.S2 B3,5')]
    walker = StackInventory(lines, [0x1000, 0x1008, 0x1010, 0x2000, 0x2100],
                            extents={0x1000: {'end': '1100'}})
    report = walker.report(0x1000)
    assert [f['entry'] for f in report['functions']] == ['0x1000', '0x2000']
    assert report['functions'][0]['edges'] == ['0x2000']
    assert report['functions'][0]['frame_decrements_bytes'] == 8
    assert report['functions'][0]['issues'][0]['site'] == '0x1008'
    assert report['accounted_frame_bytes'] is None


def test_evidence_verifies_unresolved_fragment_anchors(tmp_path):
    record = {'evidence': 'internal block in another owner',
              'anchors': [{'address': '1000', 'instruction': 'B.S2X A4'}]}
    path, instructions, digest = write_evidence(tmp_path, {'unresolved': {'1000': record}})
    with pytest.raises(ValueError, match='instruction anchor'):
        load_evidence(path, instructions, digest)


def test_extent_requires_its_own_entry_anchor(tmp_path):
    record = {'end': '1004', 'evidence': 'only the boundary is quoted',
              'anchors': [{'address': '1004', 'instruction': 'NOP 4'}]}
    path, instructions, digest = write_evidence(tmp_path, {'extents': {'1000': record}})
    with pytest.raises(ValueError, match='own entry/site anchor'):
        load_evidence(path, instructions, digest)


@pytest.mark.parametrize('end', ['1002', '1004'])
def test_extent_requires_a_decoded_and_quoted_end(tmp_path, end):
    record = {'end': end, 'evidence': 'unsupported boundary',
              'anchors': [{'address': '1000', 'instruction': 'B.S2X A3'}]}
    path, instructions, digest = write_evidence(tmp_path, {'extents': {'1000': record}})
    with pytest.raises(ValueError, match='end anchor'):
        load_evidence(path, instructions, digest)


def test_extent_accepts_anchored_boundaries(tmp_path):
    record = {'end': '1004', 'evidence': 'reviewed physical body', 'anchors': [
        {'address': '1000', 'instruction': 'B.S2X A3'},
        {'address': '1004', 'instruction': 'NOP 4'}]}
    path, instructions, digest = write_evidence(tmp_path, {'extents': {'1000': record}})
    assert load_evidence(path, instructions, digest)['extents']['1000'] == record


def test_evidence_rejects_mismatched_optional_elf_identity(tmp_path):
    path, instructions, digest = write_evidence(tmp_path, {'observed_elf_sha256': 'a' * 64})
    with pytest.raises(ValueError, match='ELF SHA-256'):
        load_evidence(path, instructions, digest, 'b' * 64)
    assert load_evidence(path, instructions, digest, 'a' * 64)


def test_cli_rejects_callback_elf_mismatch(tmp_path):
    import hashlib
    import json
    from tools.stack_depth import main

    dis = tmp_path / 'main.dis'
    dis.write_text('00001000 00000000 B.S2 B7\n')
    elf = tmp_path / 'main.elf'
    elf.write_bytes(b'different image')
    callbacks = tmp_path / 'callbacks.json'
    callbacks.write_text(json.dumps({
        'disassembly_sha256': hashlib.sha256(dis.read_bytes()).hexdigest(),
        'observed_elf_sha256': '0' * 64, 'sites': {}}))
    with pytest.raises(SystemExit) as error:
        main(['--dis', str(dis), '--elf', str(elf), '--resolve',
              '--callbacks', str(callbacks), '1000'])
    assert error.value.code == 2

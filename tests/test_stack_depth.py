"""Do not let incomplete stack inventories become finite safety claims."""
from tools.stack_depth import StackInventory, parse_disassembly


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
    output = tmp_path / 'nested' / 'report.json'
    main(['--dis', str(dis), '--catalog', str(catalog), '--report', str(output), '1000'])
    report = json.loads(output.read_text())
    assert report['inputs']['disassembly']['sha256'] == hashlib.sha256(dis.read_bytes()).hexdigest()
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

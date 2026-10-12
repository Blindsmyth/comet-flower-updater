"""Static boot candidate inventory and adversarial checker regression checks.
Run with --write to replace the survey; otherwise require exact reproducibility.
No function extents or semantic roles are inferred.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import check_rows as checker

ROOT = Path(__file__).resolve().parents[2]


def survey():
    ins, _ = checker.read_dis(ROOT / 'build/codex7/boot.dis')
    candidates = checker.boot_candidates(ROOT, ins)
    lines = ['# res5 boot candidate survey', '',
             'Static candidate inventory from boot.dis CALLP targets, literal .word pointers, and bootrefs.txt materialized code addresses. Targets must lie in declared TEXT sections and decode as instructions, not directives. Pointer targets can be internal labels; membership does not prove a function entry. Direct CALLP sites are counted, not unique caller functions. Branch-only entries and pointer tables decoded as instructions may be missing.', '',
             'Sizes, strings, and MMIO ownership are unknown for every row: no control-flow boundaries or pointer use were established. Printable fragments from decoded words and proximity to a reference are not string evidence. Roles remain guess. Evidence quotes the target instruction and all incoming candidate sources; materialized pointers are references, not calls.', '',
             '| addr | name | role | conf | evidence |', '|---|---|---|---|---|']
    for addr, sources in sorted(candidates.items()):
        calls = sum(kind == 'CALLP' for _, kind in sources)
        quote = ins[addr].replace('||', '').strip()
        sources_text = '; '.join(f'{kind} at {site}' for site, kind in sources)
        lines.append(f'| {addr} | boot_candidate_{addr} | Role unknown; size uncertain; strings unverified; MMIO unassigned; {calls} direct CALLP sites | guess | `{addr} {quote}`; {sources_text} |')
    lines += ['', '## Open questions', '', 'All entries require control-flow and semantic review before naming or promotion. No next-target distance is a function size. See docs/helpers/CODEX_REVIEW.md for manual samples and exclusions.', '']
    return '\n'.join(lines), candidates


def regression():
    cases = 0
    with tempfile.TemporaryDirectory(prefix='fwmap_') as tmp:
        for filename, addr, quote in [('res5_boot.md', 'c01f4000', 'MVK 15,B0'), ('chunk_05.md', 'c01604a0', 'STW B3,*B15--[2]'), ('chunk_08.md', 'c01604a0', 'STW B3,*B15--[2]')]:
            path = Path(tmp) / filename
            row = f'| {addr} | test_name | test | guess | `{addr} {quote}` |\n'
            mutations = {
                'baseline': (row, None),
                'wrong start': (row.replace(f'| {addr} |', f'| {int(addr,16)+1:08x} |'), 'Invalid start'),
                'nonexistent evidence': (row.replace(quote, quote).replace('` |', f'`; {int(addr,16)+1:08x} |'), 'Evidence address'),
                'wrong instruction': (row.replace(quote, 'BOGUS A0'), 'does not match'),
                'wrong operand': (row.replace(quote, quote + ',A0'), 'does not match'),
                'invalid name': (row.replace('test_name', 'bad name'), 'Invalid function name'),
                'duplicate name': (row + row, 'Duplicate name'),
                'outside quoted address': (row.replace(f'`{addr}', '`deadbeef'), 'Quoted address'),
                'hidden label bypass': (row.replace(f'| {addr} |', f'| {int(addr,16)+1:08x} |').replace('| test |', '| (hidden start) |'), 'Invalid start'),
            }
            for label, (content, expected) in mutations.items():
                path.write_text(content)
                output = Path(tmp) / 'report.txt'
                run = subprocess.run([sys.executable, str(ROOT / 'tools/fwmap/check_rows.py'), str(path), '--output', str(output)], capture_output=True, text=True)
                report = output.read_text()
                assert (run.returncode == 0) if expected is None else (run.returncode == 1 and expected in report), (filename, label, run.stderr, report)
                cases += 1
                print(f'PASS {filename}: {label}')
    assert not checker.operand_prefix('A1', 'A10')
    assert checker.operand_prefix('1180bcd0', '0x1180bcd0,B3')
    assert checker.operand_prefix('0x54,B0', '0x0054,B0')
    assert not checker.operand_prefix('0x55,B0', '0x0054,B0')
    assert not checker.predicate_matches('[!B0] B target', '[ B0] B target')
    main, _ = checker.read_dis(ROOT / 'build/fw/map/main.dis')
    assert '11805b68' in checker.sequential_starts(main)
    assert 'c015e70c' in checker.sequential_starts(main)
    assert {'c0165020', 'c01687c0', '118164c0'} <= checker.reviewed_starts(main)
    print(f'{cases} temporary-file cases + 8 matching/start assertions passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    text, candidates = survey()
    path = ROOT / 'recon/map/res5_boot.md'
    if args.write:
        path.write_text(text)
    else:
        assert path.read_text() == text, 'Survey differs from evidence-derived inventory'
    print(f'{len(candidates)} candidate rows; all source edges and entry quotes reproduced')
    regression()

"""Inventory stack frames and call-graph blockers; this is NOT a stack proof.

Catalog extents and SP decrements are triage evidence. They do not model control
flow, live save-helper frames, stack switching or interrupts. Unresolved
register branches and cycles never produce a finite total.
Run: stack_depth.py [--resolve] [--report FILE] ROOT_HEX [ROOT_HEX ...]
"""
import argparse
import bisect
import csv
import hashlib
import json
import re
from pathlib import Path

HIDDEN = {0xc015a020, 0xc015a2a0, 0xc015de40, 0xc015e060, 0xc0162a60,
          0xc0162d60, 0xc0155dc0, 0xc0169170, 0xc0160820,
          0xc014a120, 0xc014a160, 0xc014a170, 0xc016b940}
SIZE = {'STW': 4, 'STDW': 8, 'STH': 2, 'STB': 1}
SAVE_HELPERS = {0xc016e020, 0xc016e000}
LIMITATIONS = [
    'Catalog extents are provisional; local control flow and repeated pushes are not bounded.',
    'Save/restore helpers can keep SP adjustments live across sibling calls.',
    'Return aliases, computed transfers and runtime pointer writers require instruction review.',
    'Task/interrupt stack switching, preemption and interrupt nesting are not modeled.',
    'Callback mappings are image observations, not proof that runtime targets are exhaustive.',
]


def parse_disassembly(text):
    instructions = []
    for line in text.splitlines():
        match = re.match(r'^([0-9a-f]{8})\s+[0-9a-f]{4,8}\s+(.*)', line)
        if match:
            instructions.append((int(match[1], 16), match[2]))
    return sorted(instructions)


def load_evidence(path, instructions, disassembly_hash):
    """Check image identity and every quoted instruction before using evidence.

    This verifies transcription/provenance, not the reviewer's interpretation.
    The caller keeps annotations as assumptions in the resulting inventory.
    """
    data = json.loads(Path(path).read_text())
    if data.get('disassembly_sha256') != disassembly_hash:
        raise ValueError('evidence does not match this disassembly SHA-256')
    by_address = dict(instructions)
    for section in ('extents', 'sites'):
        for entry, record in data.get(section, {}).items():
            if not record.get('evidence') or not record.get('anchors'):
                raise ValueError(f'{section} {entry} lacks evidence or instruction anchors')
            for anchor in record['anchors']:
                address = int(anchor['address'], 16)
                observed = by_address.get(address)
                expected = anchor['instruction']
                if observed is None or observed.split() != expected.split():
                    raise ValueError(f'{section} {entry} instruction anchor {address:#x} differs')
            start = int(entry, 16)
            if start not in by_address:
                raise ValueError(f'{section} {entry} has no instruction at its entry/site')
            if section == 'extents':
                end = int(record['end'], 16)
                if end <= start or end > max(by_address) + 4:
                    raise ValueError(f'extent {entry} has invalid exclusive end {end:#x}')
            else:
                if record.get('kind') not in ('return', 'continuation', 'stack_switch'):
                    raise ValueError(f'site {entry} has unsupported transfer kind')
                if not re.search(r'\b(?:BNOP|B)\.\S+\s+[AB]\d+\b', by_address[start]):
                    raise ValueError(f'site {entry} is not a register branch')
                if not any(int(anchor['address'], 16) == start for anchor in record['anchors']):
                    raise ValueError(f'site {entry} lacks its own branch anchor')
    return data


class StackInventory:
    def __init__(self, instructions, starts, callbacks=None, extents=None, transfers=None):
        self.instructions = instructions
        self.addresses = [a for a, _ in instructions]
        self.extents = extents or {}
        self.transfers = transfers or {}
        self.starts = sorted(set(starts) | set(self.extents))
        self.callbacks = callbacks or {}

    def analyze(self, function):
        index = bisect.bisect_right(self.starts, function)
        extent = self.extents.get(function)
        end = int(extent['end'], 16) if extent else (
            self.starts[index] if index < len(self.starts) else None)
        frame, edges, issues, assumptions = 0, set(), [], []
        if extent:
            assumptions.append({'entry': hex(function), 'kind': 'REVIEWED_EXTENT', **extent})
        if function not in self.starts:
            issues.append({'kind': 'UNCATALOGUED_ENTRY', 'site': hex(function)})
        if function not in self.addresses:
            issues.append({'kind': 'MISSING_INSTRUCTION', 'site': hex(function)})
        if end is None:
            issues.append({'kind': 'UNKNOWN_EXTENT', 'site': hex(function)})
        if issues:
            # Do not scan unknown entries through adjacent functions or data.
            return {'entry': hex(function), 'end': hex(end) if end is not None else None,
                    'frame_decrements_bytes': None, 'edges': [],
                    'issues': issues, 'assumptions': assumptions}
        start = bisect.bisect_left(self.addresses, function)
        stop = bisect.bisect_left(self.addresses, end)
        for address, line in self.instructions[start:stop]:
            match = re.search(r'\b(STW|STDW|STH|STB)\.\S+\s+\S+,\*B15--\[(\d+)\]', line)
            if match:
                frame += SIZE[match[1]] * int(match[2])
            match = re.search(r'ADDK\.\S+\s+-(0x[0-9a-f]+|\d+),B15', line)
            if match:
                frame += int(match[1], 0)
            match = re.search(r'SUB\.\S+\s+B15,(0x[0-9a-f]+|\d+),B15', line)
            if match:
                frame += int(match[1], 0)
            match = re.search(r'\b(CALLP|BNOP|B)\.\S+\s+(0x[0-9a-f]{8}|[AB]\d+)\b', line)
            if not match:
                continue
            op, target = match[1], match[2]
            if target.startswith('0x'):
                target = int(target, 16)
                if op == 'CALLP' or not function <= target < end:
                    edges.add(target)
                if target in SAVE_HELPERS:
                    issues.append({'kind': 'LIVE_SAVE_HELPER', 'site': hex(address),
                                   'target': hex(target)})
            elif address in self.transfers:
                transfer = self.transfers[address]
                assumptions.append({'site': hex(address), **transfer})
                if transfer['kind'] == 'stack_switch':
                    issues.append({'kind': 'STACK_SWITCH', 'site': hex(address)})
            elif op != 'CALLP' and target == 'B3':
                # A prior stack load or MV B3 does not prove another register
                # remains a return address at this site or across delay slots.
                continue
            elif address in self.callbacks:
                record = self.callbacks[address]
                edges.update(int(t, 16) for t in record['targets'])
                assumptions.append({'site': hex(address), **record})
            else:
                issues.append({'kind': 'INDIRECT', 'site': hex(address), 'instruction': line.strip()})
        return {'entry': hex(function), 'end': hex(end), 'frame_decrements_bytes': frame,
                'edges': sorted(edges), 'issues': issues, 'assumptions': assumptions}

    def report(self, root):
        # State is local to one root: multi-root order cannot hide issues.
        nodes, active, done, cycles = {}, [], {}, set()

        def visit(function):
            if function in active:
                cycles.add(tuple(active[active.index(function):] + [function]))
                return None
            if function in done:
                return done[function]
            node = self.analyze(function)
            nodes[function] = node
            active.append(function)
            depths = [visit(target) for target in node['edges']]
            active.pop()
            if node['issues'] or any(d is None for d in depths):
                total = None
            else:
                total = node['frame_decrements_bytes'] + max(depths, default=0)
            done[function] = total
            return total

        total = visit(root)
        functions = [{**node, 'edges': [hex(t) for t in node['edges']]}
                     for _, node in sorted(nodes.items())]
        return {'root': hex(root), 'status': 'NOT_A_STACK_PROOF',
                'stack_bound_bytes': None, 'accounted_frame_bytes': total,
                'cycles': [[hex(t) for t in cycle] for cycle in sorted(cycles)],
                'limitations': LIMITATIONS, 'functions': functions}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roots', nargs='+', type=lambda value: int(value, 16))
    parser.add_argument('--dis', type=Path, default=Path('build/fw/map/main.dis'))
    parser.add_argument('--catalog', type=Path, default=Path('build/fw/map/subsystems.tsv'))
    parser.add_argument('--resolve', action='store_true', help='use site-specific image observations')
    parser.add_argument('--callbacks', type=Path, default=Path('docs/helpers/stack_callbacks.json'))
    parser.add_argument('--extents', type=Path, help='reviewed, image-pinned function extents')
    parser.add_argument('--transfers', type=Path, help='reviewed return/continuation site annotations')
    parser.add_argument('--report', type=Path, help='save an inventory with input hashes as JSON')
    parser.add_argument('--details', action='store_true', help='print individual blockers and cycles')
    args = parser.parse_args(argv)
    inputs = {'analyzer': Path(__file__), 'disassembly': args.dis, 'catalog': args.catalog}
    disassembly = args.dis.read_text()
    instructions = parse_disassembly(disassembly)
    disassembly_hash = hashlib.sha256(args.dis.read_bytes()).hexdigest()
    callbacks = {}
    if args.resolve:
        inputs['callbacks'] = args.callbacks
        data = json.loads(args.callbacks.read_text())
        expected = data.get('disassembly_sha256')
        if not expected or disassembly_hash != expected:
            parser.error('callback observations do not match this disassembly SHA-256')
        callbacks = {int(site, 16): record for site, record in data['sites'].items()}
    overrides = {}
    for name in ('extents', 'transfers'):
        path = getattr(args, name)
        if path:
            inputs[name] = path
            try:
                data = load_evidence(path, instructions, disassembly_hash)
                section = 'extents' if name == 'extents' else 'sites'
                if not isinstance(data.get(section), dict):
                    raise ValueError(f'{name} evidence lacks a {section} object')
            except ValueError as error:
                parser.error(str(error))
            overrides[name] = {int(entry, 16): record for entry, record in data[section].items()}
    with args.catalog.open() as stream:
        starts = {int(row['addr'], 16) for row in csv.DictReader(stream, delimiter='\t')}
    inventory = StackInventory(instructions, starts | HIDDEN, callbacks,
                               overrides.get('extents'), overrides.get('transfers'))
    reports = [inventory.report(root) for root in args.roots]
    for report in reports:
        functions = report['functions']
        issues = [issue for function in functions for issue in function['issues']]
        assumptions = sum(len(function['assumptions']) for function in functions)
        print(f"{report['root']}: NOT_A_STACK_PROOF; {len(functions)} functions, "
              f"{len(issues)} blockers, {len(report['cycles'])} cycles, {assumptions} assumptions")
        if args.details:
            for issue in issues:
                print(' ', issue['kind'], issue['site'], issue.get('instruction', issue.get('target', '')))
            for cycle in report['cycles']:
                print('  CYCLE', ' -> '.join(cycle))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        result = {'schema_version': 1, 'inputs': {name: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                             for name, path in inputs.items()}, 'reports': reports}
        args.report.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()

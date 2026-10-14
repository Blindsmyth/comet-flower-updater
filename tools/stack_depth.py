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


class StackInventory:
    def __init__(self, instructions, starts, callbacks=None):
        self.instructions = instructions
        self.addresses = [a for a, _ in instructions]
        self.starts = sorted(set(starts))
        self.callbacks = callbacks or {}

    def analyze(self, function):
        index = bisect.bisect_right(self.starts, function)
        end = self.starts[index] if index < len(self.starts) else None
        frame, edges, issues, assumptions = 0, set(), [], []
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
                    'issues': issues, 'assumptions': []}
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
    parser.add_argument('--report', type=Path, help='save an inventory with input hashes as JSON')
    parser.add_argument('--details', action='store_true', help='print individual blockers and cycles')
    args = parser.parse_args(argv)
    inputs = {'analyzer': Path(__file__), 'disassembly': args.dis, 'catalog': args.catalog}
    callbacks = {}
    if args.resolve:
        inputs['callbacks'] = args.callbacks
        data = json.loads(args.callbacks.read_text())
        expected = data.get('disassembly_sha256')
        if not expected or hashlib.sha256(args.dis.read_bytes()).hexdigest() != expected:
            parser.error('callback observations do not match this disassembly SHA-256')
        callbacks = {int(site, 16): record for site, record in data['sites'].items()}
    with args.catalog.open() as stream:
        starts = {int(row['addr'], 16) for row in csv.DictReader(stream, delimiter='\t')}
    inventory = StackInventory(parse_disassembly(args.dis.read_text()), starts | HIDDEN, callbacks)
    reports = [inventory.report(root) for root in args.roots]
    for report in reports:
        functions = report['functions']
        issues = [issue for function in functions for issue in function['issues']]
        assumptions = sum(len(function['assumptions']) for function in functions)
        print(f"{report['root']}: NOT_A_STACK_PROOF; {len(functions)} functions, "
              f"{len(issues)} blockers, {len(report['cycles'])} cycles, {assumptions} site assumptions")
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

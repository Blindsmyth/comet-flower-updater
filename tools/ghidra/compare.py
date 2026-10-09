import glob,re,os
import sys; B=sys.argv[1] if len(sys.argv)>1 else 'build/ghidra_test'
g={}
for l in open(f'{B}/functions.txt'):
    a,n,name=l.split(None,2); g[int(a,16)]=int(n)
ours=set(int(l.split('\t')[0],16) for l in list(open('build/fw/map/coverage.tsv'))[1:])
rows=set()
for f in glob.glob('recon/map/chunk_*.md'):
    for l in open(f,encoding='utf-8'):
        m=re.match(r'\| ([0-9a-f]{8}) \|',l)
        if m: rows.add(int(m.group(1),16))
hid=[int(l.split()[0],16) for l in open('build/ghidra_test/hidden_starts.txt')]
code=lambda a: (0xc0100000<=a<0xc0200000) or (0x11800000<=a<0x11840000)
gs=set(a for a in g if code(a))
print('ghidra functions (code range):',len(gs),' fact-sheet functions:',len(ours),' map rows:',len(rows))
print('fact-sheet starts also in ghidra:',len(ours&gs),'/',len(ours))
print('hidden starts ghidra finds:',sum(h in gs for h in hid),'/',len(hid))
nr=[h for h in hid if h not in rows]
print('hidden starts with no map row:',len(nr),' of those ghidra finds:',sum(h in gs for h in nr))
extra=sorted(gs-ours-rows-set(hid))
print('ghidra-only starts (not in facts/rows/hidden):',len(extra), ' e.g.',' '.join('%08x'%a for a in extra[:12]))
missing=sorted(ours-gs)
print('fact-sheet starts ghidra misses:',len(missing),' e.g.',' '.join('%08x'%a for a in missing[:12]))

"""Resolve MVK(L)/MVKH address pairs in a dis6x listing.
refs.py <main.dis> -> prints addr_ref lines: <insn_addr> <reg> <value>"""
import re, sys
lines=open(sys.argv[1]).read().splitlines()
rx=re.compile(r"^([0-9a-f]{8})\s+[0-9a-f]{8}\s+(?:\|\|)?\s*(?:\[[!AB0-9]+\]\s*)?(MVKL|MVKH|MVK)\.\S+\s+(-?0x[0-9a-fA-F]+|-?\d+),([AB]\d+)")
recent={}
out=[]
for ln in lines:
    m=rx.match(ln)
    if not m: continue
    a,op,v,r=int(m[1],16),m[2],int(m[3],0),m[4]
    if op in("MVK","MVKL"): recent[r]=(a,v&0xffff)
    elif r in recent and a-recent[r][0]<=64:
        out.append((recent[r][0],r,(v&0xffff0000)|recent[r][1]))
for a,r,v in out: print(f"{a:08x} {r} {v:08x}")

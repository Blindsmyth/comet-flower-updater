"""List calls to a function with constant register arguments (window heuristic).
calls.py <main.dis> <target_hex> [regs...]"""
import re, sys
lines=open(sys.argv[1]).read().splitlines()
tgt=sys.argv[2].lower(); regs=sys.argv[3:] or ["A4","B4","A6","B6","A8","B8","A10","B10"]
ins=re.compile(r"^([0-9a-f]{8})\s+[0-9a-f]{4,8}\s+(\|\|)?\s*(\[[!AB0-9 ]+\])?\s*(\S+)\s*(.*)$")
parsed=[]
for ln in lines:
    m=ins.match(ln)
    if m: parsed.append((int(m[1],16),m[4],m[5]))
for i,(a,op,arg) in enumerate(parsed):
    if not (op.startswith("CALL") or op.startswith("B")) or tgt not in arg.lower(): continue
    win=parsed[max(0,i-24):i+8]
    vals={}
    lo={}
    for (b,o,ar) in win:
        mm=re.match(r"(-?0x[0-9a-fA-F]+|-?\d+),([AB]\d+)$",ar.strip())
        if not mm: continue
        v,r=int(mm[1],0),mm[2]
        if o.startswith("MVKH"): vals[r]=(v&0xffff0000)|lo.get(r,0)
        elif o.startswith("MVK"): lo[r]=v&0xffff; vals[r]=v
    print(f"{a:08x}", " ".join(f"{r}={vals[r]:#x}" if isinstance(vals.get(r),int) and vals[r]>0xffff else f"{r}={vals.get(r)}" for r in regs))

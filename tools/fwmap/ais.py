"""TI AIS boot image parser: sections(path) -> (bytes, [(load_addr, size, file_off), ("entry", addr, off)]).
ais.py <image.bin>... prints the section table."""
import struct, sys
def sections(path):
    d=open(path,"rb").read(); w=lambda o: struct.unpack_from("<I",d,o)[0]
    o=4; out=[]
    while o<len(d):
        c=w(o); o+=4; lo=c&0xff
        if lo==0x63: continue
        if lo==0x01:
            a,n=w(o),w(o+4); out.append((a,n,o+8)); o+=8+((n+3)&~3)
        elif lo==0x0d:
            na=w(o)>>16; o+=4+4*na
        elif lo==0x06:
            out.append(("entry",w(o),o)); break
        else: raise SystemExit(f"unknown {c:#x} at {o-4:#x}")
    return d,out
if __name__=="__main__":
    for f in sys.argv[1:]:
        d,s=sections(f); print("==",f)
        for a,n,o in s: print(f"  {a if isinstance(a,str) else hex(a)}  size {n:#x}  file {o:#x}")

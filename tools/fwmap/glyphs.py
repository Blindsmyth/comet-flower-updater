"""Render a fixed-size page-major glyph run: glyphs.py <addr_hex> <w> <pages> <count> <out>"""
import sys
from PIL import Image
d=open("build/fw/res1_493412.bin","rb").read()
a,w,pg,n,out=int(sys.argv[1],16),int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),sys.argv[5]
o=a-0xc016f780+0x63708; S=3; per=16
im=Image.new("L",(per*(w+2)*S,((n+per-1)//per)*(pg*8+3)*S),40); px=im.load()
for g in range(n):
    gx,gy=(g%per)*(w+2),(g//per)*(pg*8+3)
    for p in range(pg):
        for c in range(w):
            b=d[o+g*w*pg+p*w+c]
            for bit in range(8):
                if b>>bit&1:
                    for i in range(S):
                        for j in range(S): px[(gx+c)*S+i,(gy+p*8+bit)*S+j]=255
im.save(out)

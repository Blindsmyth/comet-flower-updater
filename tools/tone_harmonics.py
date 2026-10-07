"""Harmonics and non-harmonic content of a probe-tone recording, per section.
Used for VPB_2026-10-06_204400 (Probe 10 440 Hz tone into CF 808, CF 808X,
TS Drive). Edit `segs` and the input file for another take.
"""
import numpy as np
r=np.load("build/agy3/take2.npy")  # right channel of the take, saved as .npy; sr=44100; f0=440.0
segs=[("tone alone",1.5,6.5),("1st: CF 808",8.0,13.0),("2nd: CF 808X",16.0,21.0),("3rd: TS Drive",23.5,29.5),("tone alone (end)",31.0,33.5)]
for name,a,b in segs:
    y=r[int(a*sr):int(b*sr)]; y=y-y.mean()
    w=np.blackman(len(y)); S=np.abs(np.fft.rfft(y*w))**2; F=np.fft.rfftfreq(len(y),1/sr)
    # refine f0 from the peak
    i=np.argmax(S*(np.abs(F-f0)<5)); f1=F[i]
    harm=[]; mask=np.abs(F)<20
    for k in range(1,int(20000/f1)+1):
        m=np.abs(F-k*f1)<3; harm.append(S[m].sum()); mask|=m
    harm=np.array(harm); band=(F>20)&(F<20000)
    rest=S[band&~mask].sum()
    # split the non-harmonic part: low (<2k, mostly noise/hum) vs high (aliasing shows up broadly)
    hi=S[band&~mask&(F>2000)].sum()
    thd=10*np.log10(harm[1:].sum()/harm[0])
    hd=" ".join("%5.1f"%(10*np.log10(h/harm[0]+1e-20)) for h in harm[1:8])
    print(f"{name:18s} level {10*np.log10(harm[0])-10*np.log10((w**2).sum())+3:6.1f} dB  THD {thd:6.1f} dB  H2..H8 [{hd}]  non-harmonic {10*np.log10(rest/harm.sum()):6.1f} dB (above 2 kHz {10*np.log10(hi/harm.sum()):6.1f})")

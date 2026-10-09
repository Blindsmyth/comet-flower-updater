/* mufft.c - "CF MuffT": times the CF Muff kernel (muff_g1.h) twice per block
 * on the pedal (cache-cold vs warm) and reports by tone code. Diagnostic only.
 * Knobs fixed at full Sustain, Tone at noon (the clip stages' worst case). */
#include "muff_g1.h"
#define MPT_STATE      MuffState
#define MPT_COEFFS     MuffCoeffs
#define MPT_SETUP(k)   muff_coeffs((k), 1.0f, 0.5f, 0.4f)
#define MPT_PROCESS(st, k, x) muff_process((st), (k), (x))
#define MPT_TAG        0x4d554646u   /* 'MUFF' */
#include "mp_timing.h"

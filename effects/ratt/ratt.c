/* ratt.c - "CF RATT": times the CF RAT kernel (rat_g1.h) twice per block on
 * the pedal (cache-cold vs warm) and reports by tone code. Diagnostic only. */
#include "rat_g1.h"
#define MPT_STATE      RatState
#define MPT_COEFFS     RatCoeffs
#define MPT_SETUP(k)   rat_coeffs((k), 10.0f, 1.0f, 1.0f)
#define MPT_PROCESS(st, k, x) rat_process((st), (k), (x))
#define MPT_TAG        0x52415420u   /* 'RAT ' */
#include "mp_timing.h"

/* t808.c - "CF 808T": times the CF 808 kernel (ts808_exact.h, the 808X
 * table solver) twice per block on the pedal (cache-cold vs warm) and
 * reports by tone code. Diagnostic only. */
#include "ts808_exact.h"
#define MPT_STATE      TsxState
#define MPT_COEFFS     TsxCoeffs
#define MPT_SETUP(k)   tsx_coeffs((k), 10.0f, 1.0f, 0.5f)
#define MPT_PROCESS(st, k, x) tsx_process((st), (k), (x))
#define MPT_TAG        0x38303820u   /* '808 ' */
#include "mp_timing.h"

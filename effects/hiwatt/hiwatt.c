/* hiwatt.c - "CF Watt" (file DR103): the Hiwatt DR103 Custom 100 circuit model
 * (hiwatt_amp.h, a port of Comet Flower's desktop amp) as a G1 effect.
 * The kernel lives in hiwatt_kernel.h (shared with the dr103diag build).
 * 2x oversampling (owner decision 2026-10-18, docs/CF_AB_2026-10-18.md): same
 * harmonics as 4x, the extra aliasing inaudible in blind tests on clean takes,
 * 25.1k instead of 41.0k cycles per block cranked. effects/hiwatt2x is now the
 * same thing; build 4x with HW_OS 4 for comparisons. */
#ifndef HW_OS
#define HW_OS 2
#endif
#include "hiwatt_kernel.h"

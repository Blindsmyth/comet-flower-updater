/* diag.c - "DR103D": DR103's processing timed on the pedal. The output is a
 * triangle at cycles/100 Hz: 0.5 s whole block, 0.5 s network derivation.
 * Diagnostic only: never save it in a patch. */
#define HW_DIAG 1
#include "hiwatt_kernel.h"

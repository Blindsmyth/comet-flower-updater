/* hiwatt2x.c - "CF Watt2x": CF Watt (hiwatt.c) built at 2x oversampling instead of 4x,
 * to measure what 4x buys (tools/ua_ab.py: same test tones through both, over USB). */
#define HW_OS 2
#include "hiwatt_kernel.h"

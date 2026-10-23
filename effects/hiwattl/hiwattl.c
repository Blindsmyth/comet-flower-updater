/* hiwattl.c - "CF WattL": CF Watt with the cheaper amp core (hiwatt_lite.h), 2x oversampling.
 * Same kernel (knob smoothing, cached networks, bypass) as CF Watt. */
#define HW_OS 2
#define HW_AMP_FILE "hiwatt_lite.h"
#include "hiwatt_kernel.h"

/* Host-only harness for the bench tap with the slot watchdog (UA_WATCHDOG). Never link into the pedal. */
#define UA_WATCHDOG
#define UA_WD_LIMIT 1000u
#define UA_WD_TRIPS 4u
#include "host_harness_tap8_bench.c"

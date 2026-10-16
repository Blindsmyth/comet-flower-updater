/* Host-only: host_harness_tap.c built as the diagnostic pattern tap
   (make_usb_audio_fw.py --tap-pattern). Never compile/link into the pedal. */
#define UA_TAP_PATTERN
#include "host_harness_tap.c"

EXPORT void host_pattern_reset(void)
{
    ua_pattern_frame = ua_pattern_phase = 0;
}

/* Host-only harness for the 10-channel tap (UA_NCH 10: FX layout, every pair usable). Never link into the pedal. */
#define UA_NCH 10
#define UA_STEMS
#define UA_FX
#ifdef _MSC_VER
__declspec(dllexport) void usb_audio_build_descriptors(void);
__declspec(dllexport) unsigned int usb_audio_copy_descriptors(unsigned char *, unsigned int, unsigned int);
#endif
#include "host_harness_tap.c"

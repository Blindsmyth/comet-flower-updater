/* Host-only harness for the 8-channel "pairs" tap (UA_PAIRS8: 7-8 DI on both). Never link into the pedal. */
#define UA_NCH 8
#define UA_STEMS
#define UA_FX
#define UA_PAIRS8
#ifdef _MSC_VER
__declspec(dllexport) void usb_audio_build_descriptors(void);
__declspec(dllexport) unsigned int usb_audio_copy_descriptors(unsigned char *, unsigned int, unsigned int);
#endif
#include "host_harness_tap.c"

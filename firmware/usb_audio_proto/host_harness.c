/* Host-only in-memory MMIO harness. Never compile/link this into the pedal.
   No operating-system or device APIs and no C runtime are used. */
#ifdef _MSC_VER
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static unsigned int registers[0x1000 / 4];
static unsigned int trace_address[512], trace_width[512], trace_count;
static unsigned int trace_overflow;

static volatile void *host_register(unsigned int address, unsigned int width)
{
    if (trace_count < 512) {
        trace_address[trace_count] = address;
        trace_width[trace_count++] = width;
    } else {
        trace_overflow = 1;
    }
    return (volatile unsigned char *)registers + (address - 0x01e00000u);
}

#define USB_AUDIO_REG8(a)  (*(volatile unsigned char *)host_register(a, 1))
#define USB_AUDIO_REG16(a) (*(volatile unsigned short *)host_register(a, 2))
#define USB_AUDIO_REG32(a) (*(volatile unsigned int *)host_register(a, 4))

EXPORT void usb_audio_build_descriptors(void);
EXPORT unsigned int usb_audio_copy_descriptors(unsigned char *, unsigned int,
                                              unsigned int);
EXPORT void usb_audio_sof_tick(void);
EXPORT int usb_audio_set_alt(unsigned int);
#include "usb_audio.c"

EXPORT void host_clear_trace(void)
{
    trace_count = 0;
    trace_overflow = 0;
}

EXPORT void host_reset(void)
{
    unsigned int i;
    for (i = 0; i < 0x1000 / 4; ++i)
        registers[i] = 0;
    usb_audio_state.if2_alt = usb_audio_state.if3_alt = 0;
    usb_audio_state.stream_enabled = usb_audio_state.frame_phase = 0;
    usb_audio_state.missed_sof = usb_audio_state.serviced_sof = 0;
    host_clear_trace();
    usb_audio_build_descriptors();
}

EXPORT void host_set_register(unsigned int address, unsigned int value)
{
    /* Aligned halfword accesses suffice for the endpoint status used by tests. */
    *(unsigned short *)((unsigned char *)registers + address - 0x01e00000u) =
        (unsigned short)value;
}

EXPORT unsigned int host_get_register(unsigned int address)
{
    return *(unsigned short *)((unsigned char *)registers + address - 0x01e00000u);
}

EXPORT unsigned int host_get_state(unsigned int index)
{
    switch (index) {
    case 0: return usb_audio_state.if2_alt;
    case 1: return usb_audio_state.if3_alt;
    case 2: return usb_audio_state.stream_enabled;
    case 3: return usb_audio_state.frame_phase;
    case 4: return usb_audio_state.missed_sof;
    case 5: return usb_audio_state.serviced_sof;
    default: return 0xffffffffu;
    }
}

EXPORT unsigned int host_trace_count(void) { return trace_count; }
EXPORT unsigned int host_trace_overflow(void) { return trace_overflow; }
EXPORT unsigned int host_trace_address(unsigned int i)
{
    return i < trace_count ? trace_address[i] : 0;
}
EXPORT unsigned int host_trace_width(unsigned int i)
{
    return i < trace_count ? trace_width[i] : 0;
}

EXPORT const unsigned char *host_fragment(unsigned int i)
{
    return i < DESC_COUNT ? desc_ptrs[i] : (const unsigned char *)0;
}

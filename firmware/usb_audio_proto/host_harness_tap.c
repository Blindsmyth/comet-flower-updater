/* Host-only harness for usb_audio_tap.c. Never compile/link this into the
   pedal. In-memory MMIO; every EP1 FIFO write is logged so tests can check
   packet payloads. The planar TX buffers and the stock pack are host stubs. */
#ifdef _MSC_VER
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static unsigned int registers[0x1000 / 4];
static unsigned int fifo_log[4096], fifo_count, fifo_overflow, fifo_sink;

static volatile void *host_register(unsigned int address)
{
    if (address == 0x01e00424u) {
        if (fifo_count < 4096)
            return &fifo_log[fifo_count++];
        fifo_overflow = 1;
        return &fifo_sink;
    }
    return (volatile unsigned char *)registers + (address - 0x01e00000u);
}

#define USB_AUDIO_REG8(a)  (*(volatile unsigned char *)host_register(a))
#define USB_AUDIO_REG16(a) (*(volatile unsigned short *)host_register(a))
#define USB_AUDIO_REG32(a) (*(volatile unsigned int *)host_register(a))

static int host_tx_l[16], host_tx_r[16];
static unsigned int host_pack_calls;
static void host_stock_pack(void) { host_pack_calls++; }

#define UA_TAP_TX_L ((const volatile int *)host_tx_l)
#define UA_TAP_TX_R ((const volatile int *)host_tx_r)

/* 8-channel sources (UA_NCH 8): dry ADC words and the float mix buses. */
#ifdef _MSC_VER
int _fltused = 0;   /* floats without the CRT (/NODEFAULTLIB) */
#endif
static int host_rx_l[16], host_rx_r[16];
static float host_bus_l[16], host_bus_r[16], host_bus_m[16], host_bus_x[16];
#define UA_TAP_RX_L ((const volatile int *)host_rx_l)
#define UA_TAP_RX_R ((const volatile int *)host_rx_r)
#define UA_TAP_BUS_L ((const volatile float *)host_bus_l)
#define UA_TAP_BUS_R ((const volatile float *)host_bus_r)
#define UA_TAP_BUS_M ((const volatile float *)host_bus_m)
#define UA_TAP_BUS_X ((const volatile float *)host_bus_x)
#define UA_TAP_STOCK_PACK() host_stock_pack()

EXPORT void usb_audio_sof_tick_tap(void);
EXPORT void ua_tx_pack_tap(void);
EXPORT int usb_audio_set_alt(unsigned int);
#include "usb_audio_tap.c"

EXPORT void host_reset(void)
{
    unsigned int i;
    for (i = 0; i < 0x1000 / 4; ++i)
        registers[i] = 0;
    for (i = 0; i < UA_TAP_FRAMES * UA_WPF; ++i)
        usb_audio_ring[i] = 0;
    usb_audio_state.if2_alt = usb_audio_state.if3_alt = 0;
    usb_audio_state.stream_enabled = usb_audio_state.frame_phase = 0;
    usb_audio_state.missed_sof = usb_audio_state.serviced_sof = 0;
    usb_audio_tap.ring_wr = usb_audio_tap.ring_rd = usb_audio_tap.primed = 0;
    usb_audio_tap.blocks = usb_audio_tap.overruns = 0;
    usb_audio_tap.underruns = usb_audio_tap.packets45 = 0;
    fifo_count = fifo_overflow = 0;
    host_pack_calls = 0;
}

/* Sets the 16-frame block the next ua_tx_pack_tap() call will see. */
EXPORT void host_set_block(const int *l, const int *r)
{
    unsigned int i;
    for (i = 0; i < 16; ++i) {
        host_tx_l[i] = l[i];
        host_tx_r[i] = r[i];
    }
}

/* Sets the 8-channel extra sources for the next block. */
EXPORT void host_set_sources(const int *rx_l, const int *rx_r, const float *bl,
                             const float *br, const float *bm, const float *bx)
{
    unsigned int i;
    for (i = 0; i < 16; ++i) {
        host_rx_l[i] = rx_l[i];
        host_rx_r[i] = rx_r[i];
        host_bus_l[i] = bl[i];
        host_bus_r[i] = br[i];
        host_bus_m[i] = bm[i];
        host_bus_x[i] = bx[i];
    }
}

EXPORT void host_set_register(unsigned int address, unsigned int value)
{
    *(unsigned short *)((unsigned char *)registers + address - 0x01e00000u) =
        (unsigned short)value;
}

EXPORT unsigned int host_get_register(unsigned int address)
{
    return *(unsigned short *)((unsigned char *)registers + address - 0x01e00000u);
}

/* Moves the logged FIFO words out and clears the log. */
EXPORT unsigned int host_take_fifo(unsigned int *out, unsigned int capacity)
{
    unsigned int i, n = fifo_count < capacity ? fifo_count : capacity;
    for (i = 0; i < n; ++i)
        out[i] = fifo_log[i];
    fifo_count = 0;
    return n;
}

EXPORT unsigned int host_fifo_overflow(void) { return fifo_overflow; }
EXPORT unsigned int host_pack_count(void) { return host_pack_calls; }

EXPORT unsigned int host_tap_state(unsigned int index)
{
    switch (index) {
    case 0: return usb_audio_tap.ring_wr;
    case 1: return usb_audio_tap.ring_rd;
    case 2: return usb_audio_tap.primed;
    case 3: return usb_audio_tap.blocks;
    case 4: return usb_audio_tap.overruns;
    case 5: return usb_audio_tap.underruns;
    case 6: return usb_audio_tap.packets45;
    case 7: return usb_audio_state.missed_sof;
    case 8: return usb_audio_state.serviced_sof;
    default: return 0xffffffffu;
    }
}

EXPORT unsigned int host_tap_sample(int x) { return ua_tap_sample(x); }

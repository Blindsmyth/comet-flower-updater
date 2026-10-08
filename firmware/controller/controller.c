/* USB MIDI controller mode for the G1X Four main firmware (v2.00).
 *
 * Loaded by an extra AIS section into free SDRAM (see controller.cmd and
 * recon/17). Three stock calls are redirected here by direct CALLP:
 *   c0134e14 CALLP c015d428 -> controller_start    (MainApp start-up)
 *   c0134df0 CALLP c0127fe0 -> controller_dispatch (MainApp event dispatch)
 *   c015ffd0 CALLP c014aef4 -> controller_analog   (calibrated expression)
 *
 * The state is initialised by the AIS load itself (mode 0 = stock), so any
 * hook that runs before controller_start takes the stock path.
 *
 * Policy (v1): hold GPIO0 (switch bitmap bit 9; likely the Rhythm/Looper
 * button, recon/15) at power-up to enter
 * controller mode for this boot. MIDI channel 1. Footswitches CC20/21,
 * the ten normal buttons CC22..31 (127 press, 0 release), knobs CC40..43
 * absolute 0..127 starting at 64, expression CC11. Physical legends are
 * unverified (recon/17 A5).
 *
 * Transport: c01274cc is the stock serialized MIDI send. Its outer lock
 * (B14[161]) waits with no timeout, and what does not fit the 1024-byte ring
 * is dropped (recon/17 A3, recon/18 1.6). Both hooks run in tasks (MainApp,
 * AD task), so v1 calls it directly; a bounded transmitter task is the
 * planned replacement.
 */
typedef unsigned char u8;
typedef unsigned int u32;

typedef struct { volatile u8 mode, entry_held; u8 knob[4]; } State;

#pragma DATA_SECTION(ctl_state, ".ctl_state")
State ctl_state = { 0, 0, { 64, 64, 64, 64 } };

#define STOCK_STARTUP ((void (*)(void))0xc015d428u)
/* Writes the ten-button bitmap (bit set = released) through its argument;
   it does not return it (recon/18 1.2). */
#define READ_SWITCHES ((void (*)(u32 *))0xc0156f00u)
#define MIDI_SEND ((void (*)(const u8 *, u32))0xc01274ccu)
#define STOCK_ANALOG ((void (*)(u32))0xc014aef4u)

static void cc(u32 control, u32 value)
{
    u8 bytes[3];
    bytes[0] = 0xb0;
    bytes[1] = (u8)control;
    bytes[2] = (u8)value;
    MIDI_SEND(bytes, 3);
}

/* Stock start-up runs first: it configures the GPIOs (c0160ad8) before
   the switches are read. MainApp enters its event loop after we return. */
void controller_start(void)
{
    u32 a = ~0u, b = ~0u;
    STOCK_STARTUP();
    READ_SWITCHES(&a);
    READ_SWITCHES(&b);
    /* GPIO0 (bit 9) low on two reads; not a timed debounce. */
    if (((a | b) & 512u) == 0) {
        ctl_state.entry_held = 1;
        ctl_state.mode = 1;
    }
}

/* Called from controller_dispatch (controller_hooks.asm) in controller
 * mode only; event points at the stock event record. */
void controller_event(const int *event)
{
    int id = event[0];
    if (ctl_state.entry_held && (id == 23 || id == 24)) {
        if (id == 24)
            ctl_state.entry_held = 0;
        return;
    }
    if (id >= 25 && id <= 28) {
        int index = id - 25, old = ctl_state.knob[index], d = event[2], value;
        if (d > 127 - old)
            value = 127;
        else if (d < -old)
            value = 0;
        else
            value = old + d;
        ctl_state.knob[index] = (u8)value;
        if (value != old)
            cc(40u + (u32)index, (u32)value);
    } else if (id >= 0 && id <= 3) {
        cc(20u + (u32)(id / 2), (id & 1) ? 0u : 127u);
    } else if (id >= 5 && id <= 24) {
        cc(22u + (u32)((id - 5) / 2), ((id - 5) & 1) ? 0u : 127u);
    }
    /* Combined gesture (4), sentinels, repeats and system events are
       consumed without output. */
}

void controller_analog(u32 value)
{
    if (!ctl_state.mode) {
        STOCK_ANALOG(value);
        return;
    }
    if (value <= 127u)
        cc(11, value);
}

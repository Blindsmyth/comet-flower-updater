/* USB MIDI controller mode for the G1X Four main firmware (v2.00).
 *
 * Loaded by an extra AIS section into free SDRAM (see controller.cmd and
 * recon/17). Four stock calls are redirected here by direct CALLP:
 *   c0134e14 CALLP c015d428 -> controller_start    (MainApp start-up)
 *   c0134df0 CALLP c0127fe0 -> controller_dispatch (MainApp event dispatch)
 *   c015ffd0 CALLP c014aef4 -> controller_analog   (calibrated expression)
 *   c0134dc4 CALLP c01537f4 -> controller_housekeeping (MainApp loop pass)
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
 * Transport (recon/19): hooks never send. They record the latest knob and
 * expression values and queue button edges; controller_drain sends them from
 * MainApp's housekeeping call (fourth hook, c0134dc4 CALLP c01537f4), only
 * when a read-only peek estimates enough ring space. The stock send
 * c01274cc can still wait on its locks in MainApp, and another producer can
 * invalidate the peek. The AD task requests a MainApp wake with a
 * zero-timeout idle event (42) when an expression value becomes pending.
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
#define STOCK_HOUSEKEEPING ((void (*)(void))0xc01537f4u)
/* Mailbox post (handle, message, timeout); stock posts to MainApp's
   mailbox B14[162] = *(c0185088) with timeout 0 at 1180a840. */
#define MBX_POST ((int (*)(u32, void *, int))0xc0166780u)
#define MAINAPP_MBX (*(volatile u32 *)0xc0185088u)
#define EVENT_IDLE 42          /* the MainApp loop skips it, then runs housekeeping */

/* Stock MIDI ring c0117b28: read index +0, write index +4, 1025 positions
   (wrap after index 1024), full when next write == read (recon/17 A3). */
#define RING ((volatile u32 *)0xc0117b28u)
#define RING_POSITIONS 1025u

/* ---- Pending output: written by the hooks, sent by controller_drain ---- */

#define BTN_QLEN 16u
#pragma DATA_SECTION(tx, ".ctl_state")
struct {
    u8 knob_dirty;                     /* bit i: knob i value unsent */
    u8 knob_value[4];
    u8 btn_head, btn_tail;             /* MainApp task only */
    u8 btn_cc[BTN_QLEN], btn_val[BTN_QLEN];
    volatile u8 expr_dirty, expr_value; /* written by the AD task */
} tx = { 0 };

static u32 ring_free(void)
{
    u32 r = RING[0], w = RING[1];
    u32 used = w >= r ? w - r : w + RING_POSITIONS - r;
    return RING_POSITIONS - 1u - used;
}

static void send_cc(u32 control, u32 value)
{
    u8 bytes[3];
    bytes[0] = 0xb0;
    bytes[1] = (u8)control;
    bytes[2] = (u8)value;
    MIDI_SEND(bytes, 3);
}

/* Runs in MainApp after every event (hook at c0134dc4). Sends at most four
   CCs per pass when a read-only ring-space estimate shows room for three
   bytes. A competing producer can change that space before the stock send,
   whose return is hidden; whole-message delivery is not guaranteed. The
   stock send can also wait on its locks in MainApp. */
static void controller_drain(void)
{
    u32 sent = 0, i;
    while (sent < 4 && tx.btn_head != tx.btn_tail && ring_free() >= 3) {
        send_cc(tx.btn_cc[tx.btn_head], tx.btn_val[tx.btn_head]);
        tx.btn_head = (u8)((tx.btn_head + 1) & (BTN_QLEN - 1));
        sent++;
    }
    for (i = 0; i < 4 && sent < 4; i++) {
        if ((tx.knob_dirty & (1u << i)) && ring_free() >= 3) {
            tx.knob_dirty &= (u8)~(1u << i);
            send_cc(40u + i, tx.knob_value[i]);
            sent++;
        }
    }
    if (sent < 4 && tx.expr_dirty && ring_free() >= 3) {
        u32 v = tx.expr_value;
        tx.expr_dirty = 0;
        send_cc(11, v);
    }
}

void controller_housekeeping(void)
{
    STOCK_HOUSEKEEPING();
    if (ctl_state.mode)
        controller_drain();
}

static void queue_button(u32 control, u32 value)
{
    u8 next = (u8)((tx.btn_tail + 1) & (BTN_QLEN - 1));
    if (next == tx.btn_head)
        return;                         /* full: drop the newest edge */
    tx.btn_cc[tx.btn_tail] = (u8)control;
    tx.btn_val[tx.btn_tail] = (u8)value;
    tx.btn_tail = next;
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
        if (value != old) {
            tx.knob_value[index] = (u8)value;
            tx.knob_dirty |= (u8)(1u << index);
        }
    } else if (id >= 0 && id <= 3) {
        queue_button(20u + (u32)(id / 2), (id & 1) ? 0u : 127u);
    } else if (id >= 5 && id <= 24) {
        queue_button(22u + (u32)((id - 5) / 2), ((id - 5) & 1) ? 0u : 127u);
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
    if (value <= 127u) {
        u32 wake = !tx.expr_dirty;
        tx.expr_value = (u8)value;
        tx.expr_dirty = 1;
        if (wake) {
            /* One idle event per pending value requests a MainApp drain.
               Timeout 0 never waits. A failed post can leave the value
               pending until another MainApp event arrives. */
            u32 msg[4] = { EVENT_IDLE, 0, 0, 0 };
            MBX_POST(MAINAPP_MBX, msg, 0);
        }
    }
}

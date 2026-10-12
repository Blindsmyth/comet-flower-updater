/* USB MIDI controller mode for the G1X Four main firmware (v2.00).
 *
 * Loaded by an extra AIS section into free SDRAM (see controller.cmd and
 * recon/17). Five stock calls are redirected here by direct CALLP:
 *   c0134e14 CALLP c015d428 -> controller_start    (MainApp start-up)
 *   c0134df0 CALLP c0127fe0 -> controller_dispatch (MainApp event dispatch)
 *   c015ffd0 CALLP c014aef4 -> controller_analog   (calibrated expression)
 *   c01600b0 CALLP c014aef4 -> controller_analog   (second AD channel)
 *   c0149d4c CALLP c014a0cc -> controller_worker_wait (MIDI worker)
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
 * Candidate worker transport: MainApp and AD only publish packed values.
 * The MIDI worker appends complete CCs under the stock ring lock and retries
 * pending state after a finite wait. This is an offline candidate; see
 * docs/CONTROLLER_TRANSPORT_DESIGN_2026-10-11.md for remaining proof gates.
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
#define STOCK_ANALOG ((void (*)(u32))0xc014aef4u)
#define EVENT_WAIT ((int (*)(u32, u32, u32, volatile u32 *, int))0xc014a0ccu)
#define EVENT_POST ((int (*)(u32, u32))0xc014a240u)
#define INNER_PEND ((int (*)(u32))0xc014a094u)
#define INNER_POST ((int (*)(u32))0xc014a1c8u)
#define RING_APPEND ((int (*)(volatile u32 *, u32))0xc0149d74u)
#define MIDI_EVENT (*(volatile u32 *)0xc0184f68u) /* B14[90] */
#define MIDI_LOCK (*(volatile u32 *)0xc0184f64u)  /* B14[89] */
#define PORT_STATE ((volatile u32 *)0xc01152b8u)

/* Stock MIDI ring c0117b28: read index +0, write index +4, 1025 positions
   (wrap after index 1024), full when next write == read (recon/17 A3). */
#define RING ((volatile u32 *)0xc0117b28u)
#define RING_POSITIONS 1025u

/* One MainApp producer for button/knob state, one AD producer for expression,
   and one MIDI-worker consumer. All shared records are aligned 32-bit words.
   An edge is published by writing its word before advancing tail. */

#define BTN_QLEN 16u
#pragma DATA_SECTION(tx, ".ctl_state")
struct {
    volatile u32 btn_head, btn_tail;
    volatile u32 btn_edge[BTN_QLEN]; /* (button index << 8) | value */
    volatile u32 btn_desired[12];
    volatile u32 knob_record[4];     /* sequence, valid bit, value */
    volatile u32 expr_record;
    u32 btn_sent[12], knob_sent[4], expr_sent;
    u32 connected;
} tx = { 0 };

static u32 ring_free(void)
{
    u32 r = RING[0], w = RING[1];
    if (r >= RING_POSITIONS || w >= RING_POSITIONS)
        return 0;
    u32 used = w >= r ? w - r : w + RING_POSITIONS - r;
    return RING_POSITIONS - 1u - used;
}

static int port_ready(void)
{
    return PORT_STATE[3] == 1u && PORT_STATE[9] != 0u;
}

static int append_cc(u32 control, u32 value)
{
    u32 original;
    int ok = 0;
    if (INNER_PEND(MIDI_LOCK) != 0)
        return 0;
    if (port_ready() && ring_free() >= 3u) {
        original = RING[1];
        if (RING_APPEND(RING, 0xb0u) == 0 &&
            RING_APPEND(RING, control) == 0 &&
            RING_APPEND(RING, value) == 0)
            ok = 1;
        else
            RING[1] = original; /* no consumer can observe a partial CC */
    }
    INNER_POST(MIDI_LOCK);
    return ok;
}

static void queue_button(u32 control, u32 value)
{
    u32 index = control - 20u;
    u32 tail = tx.btn_tail;
    u32 next = (tail + 1u) & (BTN_QLEN - 1u);
    tx.btn_desired[index] = value;
    if (next != tx.btn_head) {
        tx.btn_edge[tail] = (index << 8) | value;
        tx.btn_tail = next;
    }
    EVENT_POST(MIDI_EVENT, 1u);
}

/* Called in the stock MIDI worker after its event wait and before its ring
   drain. A finite wait revisits pending state when a wake or reconnect event
   was missed. The caller tests bit 0 of *bits after the call. */
int controller_worker_wait(u32 event, u32 mask, u32 mode,
                           volatile u32 *bits, int timeout)
{
    int result;
    u32 sent = 0, i, head, packed, value;
    if (!ctl_state.mode)
        return EVENT_WAIT(event, mask, mode, bits, timeout);

    *bits = 0;
    result = EVENT_WAIT(event, mask, mode, bits, 100);
    if (!port_ready()) {
        if (tx.connected) {
            tx.connected = 0;
            tx.btn_head = tx.btn_tail; /* discard transient old-session edges */
        }
        return result;
    }
    if (!tx.connected) {
        tx.connected = 1;
        tx.btn_head = tx.btn_tail;
        for (i = 0; i < 12; i++)
            tx.btn_sent[i] = ~0u;
        for (i = 0; i < 4; i++)
            tx.knob_sent[i] = ~0u;
        tx.expr_sent = ~0u;
    }

    while (sent < 4u) {
        head = tx.btn_head;
        if (head != tx.btn_tail) {
            packed = tx.btn_edge[head];
            i = packed >> 8;
            value = packed & 0xffu;
            if (i >= 12u || !append_cc(20u + i, value))
                break;
            tx.btn_sent[i] = value;
            tx.btn_head = (head + 1u) & (BTN_QLEN - 1u);
        } else {
            for (i = 0; i < 12u; i++)
                if (tx.btn_sent[i] != tx.btn_desired[i])
                    break;
            if (i < 12u) {
                value = tx.btn_desired[i];
                if (!append_cc(20u + i, value))
                    break;
                tx.btn_sent[i] = value;
            } else {
                for (i = 0; i < 4u; i++)
                    if (tx.knob_record[i] &&
                        tx.knob_record[i] != tx.knob_sent[i])
                        break;
                if (i < 4u) {
                    packed = tx.knob_record[i];
                    if (!append_cc(40u + i, packed & 0xffu))
                        break;
                    tx.knob_sent[i] = packed;
                } else {
                    packed = tx.expr_record;
                    if (!packed || packed == tx.expr_sent)
                        break;
                    if (!append_cc(11u, packed & 0xffu))
                        break;
                    tx.expr_sent = packed;
                }
            }
        }
        sent++;
    }
    if (sent) {
        /* c014a0cc writes -50 to *bits on timeout. Passing -49 after a
           blind OR would feed a negative value into c0149cac/c0149ce8. */
        u32 observed = *bits;
        *bits = ((int)observed > 0 ? observed : 0u) | 1u;
    }
    return result;
}

/* Stock start-up runs first: it configures the GPIOs (c0160ad8) before
   the switches are read. MainApp enters its event loop after we return. */
void controller_start(void)
{
    u32 a = ~0u, b = ~0u, i;
    STOCK_STARTUP();
    READ_SWITCHES(&a);
    READ_SWITCHES(&b);
    /* GPIO0 (bit 9) low on two reads; not a timed debounce. */
    if (((a | b) & 512u) == 0) {
        for (i = 0; i < 4u; i++)
            tx.knob_record[i] = 0x100u | 64u;
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
            u32 prior = tx.knob_record[index];
            tx.knob_record[index] = ((prior + 0x200u) & ~0x1ffu) |
                                    0x100u | (u32)value;
            EVENT_POST(MIDI_EVENT, 1u);
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
        u32 prior = tx.expr_record;
        if ((prior & 0x100u) && (prior & 0xffu) == value)
            return;
        tx.expr_record = ((prior + 0x200u) & ~0x1ffu) |
                          0x100u | value;
        EVENT_POST(MIDI_EVENT, 1u);
    }
}

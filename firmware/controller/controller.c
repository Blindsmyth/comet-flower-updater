/* USB MIDI controller mode for the G1X Four main firmware (v2.00).
 *
 * Loaded by an extra AIS section into free SDRAM (see controller.cmd and
 * recon/17). Seven stock calls are redirected here by direct CALLP:
 *   c0134e14 CALLP c015d428 -> controller_start    (MainApp start-up)
 *   c0134df0 CALLP c0127fe0 -> controller_dispatch (MainApp event dispatch)
 *   c015ffd0 CALLP c014aef4 -> controller_analog   (calibrated expression)
 *   c01600b0 CALLP c014aef4 -> controller_analog   (second AD channel)
 *   c0149d4c CALLP c014a0cc -> controller_worker_wait (MIDI worker)
 *   c014a048 CALLP c014a1c8 -> controller_reset_unlock (ring reset)
 *   c0149fa8 CALLP c014a400 -> controller_worker_create (new transport)
 *
 * The state is initialised by the AIS load itself (mode 0 = stock), so any
 * hook that runs before controller_start takes the stock path.
 *
 * Policy (v2): hold GPIO0 (switch bitmap bit 9; likely the Rhythm/Looper
 * button, recon/15) at power-up to start in MIDI mode, or hold it for 2 s
 * at run time to switch between effects mode and MIDI mode (owner choice
 * 2026-10-16). Audio keeps running in both. In effects mode a short press
 * reaches the stock firmware on release (controller_gate). In MIDI mode
 * that button is a tap: CC31 127 then 0 on a short release. MIDI channel 1. Footswitches CC20/21,
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

#ifndef CTL_HOST   /* tests/test_controller_mode.py supplies host stubs */
#define STOCK_STARTUP ((void (*)(void))0xc015d428u)
/* Writes the ten-button bitmap (bit set = released) through its argument;
   it does not return it (recon/18 1.2). */
#define READ_SWITCHES ((void (*)(u32 *))0xc0156f00u)
#define STOCK_ANALOG ((void (*)(u32))0xc014aef4u)
#define EVENT_POST ((int (*)(u32, u32))0xc014a240u)
#define INNER_PEND ((int (*)(u32))0xc014a094u)
#define INNER_POST ((int (*)(u32))0xc014a1c8u)
#define RING_APPEND ((int (*)(volatile u32 *, u32))0xc0149d74u)
#define TASK_CREATE ((u32 (*)(u32))0xc014a400u)
#define MIDI_LOCK (*(volatile u32 *)0xc0184f64u)  /* B14[89] */
#define PORT_STATE ((volatile u32 *)0xc01152b8u)
#define TICKS (*(volatile u32 *)0xc0182054u)        /* 1 tick = 1 ms (recon/04) */
#define UA_REQUEST (*(volatile u32 *)0xc01a8004u)  /* firmware/usb_audio/ua_glue.c ua_mode.request */
/* MainApp's raw event mailbox B14[162] and its post c0166780(handle, msg,
   timeout); c01534c4 pends on it and c015350c normalizes the raw ID. The
   last fetched raw ID is kept in B14[106] (copied into record word 1). */
#define MAINAPP_MBX (*(volatile u32 *)0xc0185088u)
#define MBX_POST ((int (*)(u32, void *, int))0xc0166780u)
#define LAST_RAW_ID (*(volatile u32 *)0xc0184fa8u)

/* Stock MIDI ring c0117b28: read index +0, write index +4, 1025 positions
   (wrap after index 1024), full when next write == read (recon/17 A3). */
#define RING ((volatile u32 *)0xc0117b28u)
#endif
#define RING_POSITIONS 1025u
#define EV_MODE_PRESS 23    /* GPIO0, bitmap bit 9: 5 + 2*9 */
#define EV_MODE_RELEASE 24
#define MODE_HOLD_TICKS 2000u

/* One MainApp producer for button/knob state, one AD producer for expression,
   and one MIDI-worker consumer. All shared records are aligned 32-bit words.
   An edge is published by writing its word before advancing tail. */

#ifdef CTL_DIAG
/* Offline diagnostic build only (make_controller_fw.py --diag-teardown). */
void controller_diag_request(void);
int controller_diag_peek(u32 *control, u32 *value);
void controller_diag_commit(void);
void controller_diag_worker(u32 task);
#endif

#ifdef CTL_UI
void controller_ui_sent(u32 control, u32 value);
void controller_ui_mode(u32 mode);
u32 controller_menu_install(void);
#endif

/* Run-time mode toggle. Only MainApp touches this record. */
#pragma DATA_SECTION(sw, ".ctl_state")
struct {
    u32 down, t0;           /* mode button held since TICKS t0 */
    u32 replay;             /* a reposted release must reach stock */
    int press[4];           /* the normalized press record, held back */
    u32 msg[4];             /* raw mailbox message for the reposted release */
} sw = { 0 };

#define BTN_QLEN 16u
#pragma DATA_SECTION(tx, ".ctl_state")
struct {
    volatile u32 btn_head, btn_tail;
    volatile u32 btn_edge[BTN_QLEN]; /* (button index << 8) | value */
    volatile u32 btn_desired[12];
    volatile u32 knob_record[4];     /* sequence, valid bit, value */
    volatile u32 expr_record;
    u32 btn_sent[12], knob_sent[4], expr_sent;
    u32 connected, observed_generation;
    volatile u32 generation;       /* changed only under MIDI_LOCK */
} tx = { 0 };

/* Written only by the one live MIDI worker's assembly wait thunk. Preserve
   the supplied event across EVENT_WAIT without retaining a controller frame
   on the worker stack. Worker creation is serialized after old handles have
   been removed; a deleted old worker must never resume. Do not replace this
   with a reload of the latest global event handle after the wait. */
#pragma DATA_SECTION(controller_wait_event, ".ctl_state")
volatile u32 controller_wait_event = 0;

/* Stock init rejects any remaining worker/lock/event handles before arriving
   here and has already cleared the ring. Invalidate consumer state BEFORE
   creating the replacement worker: handle addresses may be reused. Producers
   retain their desired values; the new worker discards stale edges and replays
   those values on its first ready pass. No added kernel operation is needed. */
u32 controller_worker_create(u32 descriptor)
{
    if (ctl_state.mode)
        tx.connected = 0;
#ifdef CTL_DIAG
    {
        u32 task = TASK_CREATE(descriptor);
        controller_diag_worker(task);
        return task;
    }
#else
    return TASK_CREATE(descriptor);
#endif
}

/* c014a018 has already cleared the ring and packetizer under MIDI_LOCK.
   Publish before releasing that same lock. The worker's finite wait observes
   the token without an added event-post/scheduler call on this USB callback
   path. Preserve the stock release result and mode-off behavior. This covers
   resets through c014a018, not arbitrary/unknown writes to port or ring. */
int controller_reset_unlock(u32 lock)
{
    if (ctl_state.mode)
        tx.generation++;
    return INNER_POST(lock);
}

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

/* Caller holds MIDI_LOCK through both acceptance and sent-state commit. */
static int append_cc(u32 control, u32 value)
{
    u32 original;
    int ok = 0;
    if (port_ready() && ring_free() >= 3u) {
        original = RING[1];
        if (RING_APPEND(RING, 0xb0u) == 0 &&
            RING_APPEND(RING, control) == 0 &&
            RING_APPEND(RING, value) == 0)
            ok = 1;
        else
            RING[1] = original; /* no consumer can observe a partial CC */
    }
#ifdef CTL_UI
    if (ok)
        controller_ui_sent(control, value);
#endif
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
    /* The worker polls. Producers never acquire a kernel handle that USB
       teardown can delete between a handle load and an event post. */
}

/* The assembly controller_worker_wait tail-calls the stock finite wait, then
   tail-calls this pump with the original supplied event, worker SP+4 bits,
   and stock result. The stock worker resumes at c0149d56 after we return.
   No controller frame remains live during EVENT_WAIT or task suspension. */
int controller_worker_pump(u32 event, volatile u32 *bits, int result)
{
    u32 sent = 0, i, head, packed, value;
    if (INNER_PEND(MIDI_LOCK) != 0)
        return result;
    if (!port_ready()) {
        if (tx.connected) {
            tx.connected = 0;
            tx.btn_head = tx.btn_tail; /* discard transient old-session edges */
        }
        INNER_POST(MIDI_LOCK);
        return result;
    }
    if (!tx.connected || tx.observed_generation != tx.generation) {
        tx.connected = 1;
        tx.observed_generation = tx.generation;
        tx.btn_head = tx.btn_tail;
        for (i = 0; i < 12; i++)
            tx.btn_sent[i] = ~0u;
        for (i = 0; i < 4; i++)
            tx.knob_sent[i] = ~0u;
        tx.expr_sent = ~0u;
    }

    while (sent < 4u) {
#ifdef CTL_DIAG
        if (controller_diag_peek(&packed, &value)) {
            if (!append_cc(packed, value))
                break;
            controller_diag_commit();
            sent++;
            continue;
        }
#endif
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
    INNER_POST(MIDI_LOCK);
    /* Continue a bounded replay promptly; do not spin on a full ring. */
    if (sent == 4u)
        EVENT_POST(event, 1u); /* this worker owns the supplied live event */
    if (sent) {
        /* c014a0cc returns -50 on timeout and leaves our prezeroed *bits
           unchanged. Defensively normalize nonpositive output before
           setting the drain bit; preserve positive stock event bits. */
        u32 observed = *bits;
        *bits = ((int)observed > 0 ? observed : 0u) | 1u;
    }
    return result;
}

#ifdef CTL_UI
/* For the screen (UpdateUI): how long the mode button has been held. */
u32 controller_hold_ticks(void)
{
    u32 t0 = sw.t0;
    return sw.down ? TICKS - t0 : 0u;
}
#endif

static void enter_midi(void)
{
    u32 i;
    for (i = 0; i < 4u; i++)
        tx.knob_record[i] = ((tx.knob_record[i] + 0x200u) & ~0x1ffu) |
                            0x100u | ctl_state.knob[i];
    tx.connected = 0;       /* the worker replays every value on its next pass */
    ctl_state.mode = 1;
#ifdef CTL_UI
    controller_ui_mode(1u);
#endif
}

static void leave_midi(void)
{
    ctl_state.mode = 0;
#ifdef CTL_UI
    controller_ui_mode(0u);  /* UpdateUI redraws the stock screen */
#endif
}

#ifdef CTL_UI
/* The MODE item on our settings page (controller_menu.c). It runs in
   MainApp's event dispatch, like controller_gate. MIDI mode consumes every
   event, so only FX -> MIDI is reachable from the menu. */
u32 controller_get_mode(void)
{
    return ctl_state.mode;
}

void controller_set_mode(u32 mode)
{
    if (mode && !ctl_state.mode)
        enter_midi();
    else if (!mode && ctl_state.mode)
        leave_midi();
}
#endif

/* Effects mode, called by the dispatch hook for every normalized event
   before the stock dispatchers; nonzero consumes the event. The mode-button
   press is held back. A release after 2 s enters MIDI mode; an earlier one
   becomes the saved press, and the raw release is posted back to MainApp's
   mailbox so stock sees press then release, in order. */
int controller_gate(int *event)
{
    int id = event[0];
    if (id == EV_MODE_PRESS) {
        sw.down = 1;
        sw.t0 = TICKS;
        sw.press[0] = event[0];
        sw.press[1] = event[1];
        sw.press[2] = event[2];
        sw.press[3] = event[3];
        return 1;
    }
    if (id != EV_MODE_RELEASE)
        return 0;
    if (sw.replay) {
        sw.replay = 0;
        return 0;
    }
    if (!sw.down)
        return 0;
    sw.down = 0;
    if (TICKS - sw.t0 >= MODE_HOLD_TICKS) {
        enter_midi();
        return 1;
    }
    sw.msg[0] = EV_MODE_RELEASE;
    sw.msg[1] = sw.msg[2] = sw.msg[3] = 0;
    LAST_RAW_ID = EV_MODE_PRESS;   /* as if the press had just been fetched */
    if (MBX_POST(MAINAPP_MBX, sw.msg, 0))
        sw.replay = 1;
    event[0] = sw.press[0];
    event[1] = sw.press[1];
    event[2] = sw.press[2];
    event[3] = sw.press[3];
    return 0;
}

/* Stock start-up runs first: it configures the GPIOs (c0160ad8) before
   the switches are read. MainApp enters its event loop after we return. */
void controller_start(void)
{
    u32 a = ~0u, b = ~0u, i;
    STOCK_STARTUP();
#ifdef CTL_UI
    controller_menu_install();   /* our settings page; stock if the tables differ */
#endif
    READ_SWITCHES(&a);
    READ_SWITCHES(&b);
#ifdef CTL_UI
    /* USB-audio mode (owner: a start-up button that is not GPIO0): switch
       bit 2 (GPIO 6, events 9/10, "B3" on the MIDI screen) low on both
       reads. It is in none of the stock power-up masks (c0140c8c, table
       c0180570: aff, d7f, ff7, ffb, 3ff, fdf; bit 2 there is A7 bit 4), so
       holding it alone has no stock meaning. Only the request is written;
       the USB-audio layer latches it at the USB open, which runs after this
       (docs/helpers/USB_MODE_ASTRA_2026-10-16.md finding 3). Without that
       layer the word is unused free SDRAM. */
    if (((a | b) & 4u) == 0)
        UA_REQUEST = 1u;
#endif
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
    /* The mode button: a short press is a CC31 tap, 2 s leaves MIDI mode. */
    if (id == EV_MODE_PRESS) {
        sw.down = 1;
        sw.t0 = TICKS;
        return;
    }
    if (id == EV_MODE_RELEASE) {
        if (!sw.down)
            return;
        sw.down = 0;
        if (TICKS - sw.t0 >= MODE_HOLD_TICKS) {
            leave_midi();
        } else {
            queue_button(31u, 127u);
            queue_button(31u, 0u);
        }
        return;
    }
#ifdef CTL_DIAG
    if (id == 4)
        controller_diag_request();
#endif
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
    }
}

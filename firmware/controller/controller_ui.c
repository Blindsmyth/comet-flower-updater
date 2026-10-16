/* On-pedal status screen for controller mode (OFFLINE candidate, --ui).
 *
 * Design: docs/ONDEVICE_UI_2026-10-15.md; recon and ABI checks:
 * docs/helpers/ONDEVICE_UI_RECON_REPORT.md (Claude review).
 *
 * UpdateUI (task) blocks in c013c76c CALLP c0144580 = Event_pend(event A4,
 * andMask B4, orMask A6, timeout B6) with timeout -1; the call returns the
 * event bits, or 0 on timeout. That one CALLP is redirected here. In stock
 * mode it waits in finite slices and returns only on a real event. In controller
 * mode each timeout is also a UI tick that runs in UpdateUI's own task, where
 * stock already draws. A real event is returned unchanged (never 0, as the
 * stock infinite wait guarantees), and the next tick repaints over whatever
 * the stock handler drew.
 *
 * Producers only store words: append_cc (MIDI worker, under MIDI_LOCK)
 * calls controller_ui_sent. USB state is read here from the same
 * PORT_STATE test the worker uses; TX4 outstanding from the TX record.
 *
 * Drawing (verified against main.dis, not only the recon report):
 *   c011f8d8(ctx, 1)         clear the 512-byte page buffer 11800000+ctx*0x200
 *                            (stock c013c714 passes 0, 1)
 *   c011d2d4(ctx, ch, page, x) one 5x7 glyph: A6=page 0..3 (SHL 7), B6=x 0..127;
 *                            the caller marks the page dirty (stock c011e080)
 *   c011ec48(ctx, s, x, y)   8x13 string, x advances 9 (c011ec68), y in pixels;
 *                            draws through c011c508, which marks dirty itself
 *   gate c0161200(B14[149]) -> c016df00(ctx) flush -> c016d880(gate, key),
 *                            exactly as UpdateUI's own render c013c72c..c013c748
 * No division and no switch: the payload has no run-time support library.
 */
typedef unsigned int u32;
typedef unsigned char u8;

typedef struct { volatile u8 mode, entry_held; u8 knob[4]; } State;
extern State ctl_state;

#ifndef UI_HOST   /* tests/test_controller_ui.py supplies host stubs */
#define STOCK_PEND ((u32 (*)(u32, u32, u32, int))0xc0144580u)
#define LCD_CLEAR ((void (*)(u32, u32))0xc011f8d8u)
#define GLYPH5 ((void (*)(u32, u32, u32, u32))0xc011d2d4u)
#define TEXT8 ((void (*)(u32, const char *, u32, u32))0xc011ec48u)
#define GATE_ENTER ((u32 (*)(u32))0xc0161200u)
#define LCD_FLUSH ((void (*)(u32))0xc016df00u)
#define GATE_LEAVE ((void (*)(u32, u32))0xc016d880u)
#define LCD_GATE (*(volatile u32 *)0xc0185054u)        /* B14[149] */
#define LCD_DIRTY ((volatile u8 *)0x11813250u)         /* + ctx: page bits */
#define PORT_STATE ((volatile u32 *)0xc01152b8u)
#define TX4 ((volatile u32 *)(0xc011297cu + 0x2a8u * 4u))
#define TICKS (*(volatile u32 *)0xc0182054u)          /* SYS/BIOS tick counter */
#endif

#define CTX 0u
#define UI_TICKS 50           /* Clock ticks per UI tick (period unproven; see TICKS) */
#define STALL_TICKS 20u       /* consecutive UI ticks with TX4 outstanding */

#pragma DATA_SECTION(ui, ".ctl_state")
struct {
    volatile u32 last;        /* valid<<31 | control<<8 | value; one aligned store */
    volatile u32 sent;        /* accepted CCs */
    u32 stall;                /* consecutive ticks with TX4 outstanding */
    u32 repaint;              /* a stock event ran: paint even if unchanged */
    u32 shown[4];             /* model last painted */
} ui = { 0, 0, 0, 1, { 0, 0, 0, 0 } };

void controller_ui_sent(u32 control, u32 value)
{
    ui.last = 0x80000000u | (control << 8) | value;
    ui.sent++;
}

/* ---- text helpers ------------------------------------------------------ */

static char *put(char *p, const char *s)
{
    while (*s)
        *p++ = *s++;
    return p;
}

static char *dec(char *p, u32 v, u32 width)
{
    static const u32 pow10[] = { 1000000000u, 100000000u, 10000000u, 1000000u,
                                 100000u, 10000u, 1000u, 100u, 10u, 1u };
    u32 i, started = 0;
    for (i = 0; i < 10u; i++) {
        u32 d = 0;
        while (v >= pow10[i]) {
            v -= pow10[i];
            d++;
        }
        if (d || started || i == 9u) {
            *p++ = (char)('0' + d);
            started = 1;
        } else if (10u - i <= width) {
            *p++ = ' ';
        }
    }
    return p;
}

static char *hex(char *p, u32 v)
{
    int s;
    p = put(p, "0x");
    for (s = 28; s > 0 && !(v >> s); s -= 4)
        ;
    for (; s >= 0; s -= 4) {
        u32 n = (v >> s) & 0xfu;
        *p++ = (char)(n < 10u ? '0' + n : 'a' + n - 10u);
    }
    return p;
}

static void line5(u32 page, const char *s)
{
    u32 x = 0;
    while (*s && x <= 128u - 6u) {
        GLYPH5(CTX, (u32)(u8)*s++, page, x);
        x += 6u;
    }
    LCD_DIRTY[CTX] |= (u8)(1u << page);
}

static char *source(char *p, u32 control)
{
    if (control == 11u)
        return put(p, "EXP");
    if (control == 20u || control == 21u)
        return dec(put(p, "FS"), control - 19u, 0);
    if (control >= 22u && control <= 31u)
        return dec(put(p, "B"), control - 21u, 0);
    if (control >= 40u && control <= 43u)
        return dec(put(p, "K"), control - 39u, 0);
    return put(p, "DIAG");
}

/* ---- screens ----------------------------------------------------------- */

#ifdef CTL_DIAG
void controller_diag_ui(u32 *peak, u32 *creates, u32 *fault, u32 *teardown);
#endif

static void paint(u32 usb, u32 q, u32 last)
{
    char b[48], *p;
    LCD_CLEAR(CTX, 1u);
#ifdef CTL_DIAG
    {
        u32 peak, creates, fault, teardown;
        controller_diag_ui(&peak, &creates, &fault, &teardown);
        p = dec(put(b, "CLAUDE W#"), creates, 0);   /* the diag page: a quiet nod */
        p = dec(put(p, " t"), TICKS, 0);
        *p = 0;
        line5(0u, b);
        p = put(b, "STACK ");
        p = peak == 0xffffffffu ? put(p, "--") : dec(p, peak, 0);
        p = put(p, "/2048");
        *p = 0;
        line5(1u, b);
        p = dec(put(b, usb == 2u ? "TX STALL q" : usb ? "USB OK q" : "NO USB q"), q, 0);
        p = hex(put(p, " F"), fault);
        p = dec(put(p, " TD"), teardown, 0);
        *p = 0;
        line5(2u, b);
    }
#else
    line5(0u, usb == 2u ? "COMET FLOWER TX STALL" : usb ? "COMET FLOWER USB  CH1"
                                                       : "COMET FLOWER NO USB");
    if (last >> 31) {
        u32 control = (last >> 8) & 0x7fu, value = last & 0x7fu;
        p = dec(put(b, "CC"), control, 0);
        *p++ = ' ';
        p = source(p, control);
        *p++ = ' ';
        p = dec(p, value, 3);
        *p = 0;
        TEXT8(CTX, b, 0u, 10u);
    } else {
        TEXT8(CTX, usb ? "READY" : "CONNECT USB", 0u, 10u);
    }
#endif
    p = dec(put(b, "sent "), ui.sent, 0);
    p = dec(put(p, "  q "), q, 0);
#ifdef CTL_DIAG
    if (last >> 31) {
        p = dec(put(p, " CC"), (last >> 8) & 0x7fu, 0);
        p = dec(put(p, "="), last & 0x7fu, 0);
    }
#endif
    *p = 0;
    line5(3u, b);
    {
        u32 key = GATE_ENTER(LCD_GATE);
        LCD_FLUSH(CTX);
        GATE_LEAVE(LCD_GATE, key);
    }
}

static void tick(void)
{
    u32 ready = PORT_STATE[3] == 1u && PORT_STATE[9] != 0u;
    u32 q = TX4[5], last = ui.last, usb;
    ui.stall = ready && q ? ui.stall + (ui.stall < STALL_TICKS) : 0u;
    usb = !ready ? 0u : ui.stall >= STALL_TICKS ? 2u : 1u;
#ifdef CTL_DIAG
    ui.repaint = 1u;                   /* the tick counter changes every time */
#endif
    if (!ui.repaint && ui.shown[0] == usb && ui.shown[1] == q && ui.shown[2] == last
            && ui.shown[3] == ui.sent)
        return;
    ui.shown[0] = usb;
    ui.shown[1] = q;
    ui.shown[2] = last;
    ui.shown[3] = ui.sent;
    ui.repaint = 0u;
    paint(usb, q, last);
}

/* An infinite wait is replaced by finite waits that return only on a real
   event: the same contract for the caller in either mode. This also covers a
   wait that began before controller_start latched the mode. */
u32 controller_ui_pend(u32 event, u32 and_mask, u32 or_mask, int timeout)
{
    u32 r;
    if (timeout != -1)
        return STOCK_PEND(event, and_mask, or_mask, timeout);
    for (;;) {
        r = STOCK_PEND(event, and_mask, or_mask, UI_TICKS);
        if (r) {
            ui.repaint = 1u;
            return r;
        }
        if (ctl_state.mode)
            tick();
    }
}

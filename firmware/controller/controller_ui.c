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
/* Page buffer: byte = one 8-pixel column, bit 0 on top (c011d2d4:
   11800000 + ctx<<9 + page<<7 + x). The caller marks the page dirty. */
#define LCD_COLS ((volatile u8 *)0x11800000u)
#endif

u32 controller_hold_ticks(void);   /* controller.c: mode button held, 0 if not */
#ifdef CTL_CF_HEADER
u32 cf_header_tick(void);          /* cf_header.c */
#endif

#define CTX 0u
#define UI_TICKS 50           /* Clock ticks per UI tick (period unproven; see TICKS) */
#define STALL_TICKS 20u       /* consecutive UI ticks with TX4 outstanding */
#define HOLD_TICKS 2000u      /* matches controller.c MODE_HOLD_TICKS */
#define ANIM_TICKS 30         /* Clock ticks (1 ms each) per slide frame */
#define ANIM_ENTER 1u         /* MIDI page pushes in from the right */
#define ANIM_LEAVE 2u         /* stock screen pushes back in from the left */

#pragma DATA_SECTION(ui, ".ctl_state")
struct {
    volatile u32 last;        /* valid<<31 | control<<8 | value; one aligned store */
    volatile u32 sent;        /* accepted CCs */
    u32 stall;                /* consecutive ticks with TX4 outstanding */
    u32 repaint;              /* a stock event ran: paint even if unchanged */
    u32 shown[6];             /* model last painted */
    volatile u32 stock_redraw; /* MIDI mode was left: stock repaints its screen */
    volatile u32 anim_req;    /* ANIM_ENTER, or ANIM_LEAVE once the MIDI page is saved */
    u32 anim_dir;             /* slide running: ANIM_ENTER/ANIM_LEAVE, else 0 */
    u32 anim_frame;           /* next index into slide[] */
} ui = { 0, 0, 0, 1, { 0, 0, 0, 0, 0, 0 }, 0, 0, 0, 0 };

/* Mode-change slide, like the stock screen changes (owner request
   2026-10-16): the old frame is pushed out sideways by the new one. Both
   frames are copies of the 512-byte page buffer; slide[] is the number of
   new-frame columns visible per frame (ease-out, ~200 ms). */
static u8 anim_old[512], anim_new[512];
static const u8 slide[] = { 22, 50, 78, 100, 116, 125, 128 };
#define SLIDE_FRAMES 7u

void controller_ui_sent(u32 control, u32 value)
{
    ui.last = 0x80000000u | (control << 8) | value;
    ui.sent++;
}

/* MainApp, after it changed ctl_state.mode. UpdateUI event bit 0 is a full
   stock redraw: c013c8ba passes it to the render c013c700, whose arg bit 0
   clears the page (c011f8d8) and redraws the current screen (c013c0c8). */
void controller_ui_mode(u32 mode)
{
    if (mode) {
        ui.anim_req = ANIM_ENTER;   /* tick() paints whenever this is set */
        ui.repaint = 1u;
    } else {
        ui.stock_redraw = 1u;
    }
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

/* Columns x0..x0+w-1 of a bar on one or two pages. top/bottom are the
   outline bytes, full the filled column; fill = value*(w-2)/127 rounded,
   without a division: (value*(w-2)*258 + 2^14) >> 15 is exact for w <= 66. */
static void bar(u32 page, u32 x0, u32 w, u32 value, u8 edge, u8 full)
{
    volatile u8 *col = LCD_COLS + (CTX << 9) + (page << 7) + x0;
    u32 fill = (value * (w - 2u) * 258u + 16384u) >> 15, x;
    for (x = 0; x < w; x++)
        col[x] = x == 0u || x == w - 1u || x <= fill ? full : edge;
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
u32 controller_diag_beacons(void);
#endif

static void flush(void)
{
    u32 key = GATE_ENTER(LCD_GATE);
    LCD_FLUSH(CTX);
    GATE_LEAVE(LCD_GATE, key);
}

static void compose(u32 usb, u32 q, u32 last, u32 hold)
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
    /* MIDI-mode page (owner request 2026-10-16): what was pressed, as a
       reference, and every knob position at a glance. */
    p = put(b, usb == 2u ? "MIDI CH1 STALL" : usb ? "MIDI CH1 USB" : "MIDI CH1 NO USB");
    if (last >> 31) {
        while (p < b + 17)
            *p++ = ' ';
        p = dec(put(p, "CC"), (last >> 8) & 0x7fu, 0);
    }
    *p = 0;
    line5(0u, b);
    if (hold) {
        TEXT8(CTX, "LET GO=EFFECTS", 0u, 10u);   /* 126 px */
    } else if (last >> 31) {
        u32 control = (last >> 8) & 0x7fu, value = last & 0x7fu;
        p = source(b, control);
        *p = 0;
        TEXT8(CTX, b, 0u, 10u);
        if (control >= 20u && control <= 31u) {
            TEXT8(CTX, value ? "ON" : "OFF", 45u, 10u);
        } else {
            p = dec(b, value, 3);
            *p = 0;
            TEXT8(CTX, b, 36u, 10u);
            bar(1u, 72u, 56u, value, 0x10u, 0xf0u);   /* y 12..19 */
            bar(2u, 72u, 56u, value, 0x08u, 0x0fu);
        }
    } else {
        TEXT8(CTX, usb ? "READY" : "CONNECT USB", 0u, 10u);
    }
    {
        u32 i;
        for (i = 0; i < 4u; i++) {
            GLYPH5(CTX, '1' + i, 3u, i << 5);
            bar(3u, (i << 5) + 7u, 24u, ctl_state.knob[i], 0x42u, 0x7eu);
        }
    }
#endif
#ifdef CTL_DIAG
    p = dec(put(b, "b"), controller_diag_beacons(), 0);
    p = dec(put(p, " s"), ui.sent, 0);
    if (last >> 31) {
        p = dec(put(p, " CC"), (last >> 8) & 0x7fu, 0);
        p = dec(put(p, "="), last & 0x7fu, 0);
    }
    *p = 0;
    line5(3u, b);
#endif
}

/* ---- slide ------------------------------------------------------------- */

static void copy_frame(u8 *dst, volatile const u8 *src)
{
    u32 i;
    for (i = 0; i < 512u; i++)
        dst[i] = src[i];
}

/* One frame: n columns of the new frame are visible. ENTER: new enters at
   the right, old leaves to the left; LEAVE mirrors it. */
static void slide_frame(u32 dir, u32 n)
{
    volatile u8 *lcd = LCD_COLS + (CTX << 9);
    u32 page, x;
    for (page = 0; page < 512u; page += 128u)
        for (x = 0; x < 128u; x++) {
            u32 i = page + x;
            if (dir == ANIM_ENTER)
                lcd[i] = x + n < 128u ? anim_old[i + n] : anim_new[i + n - 128u];
            else
                lcd[i] = x < n ? anim_new[i + 128u - n] : anim_old[i - n];
        }
    LCD_DIRTY[CTX] |= 0x0fu;
    flush();
}

/* Starts a slide from anim_old to the frame now in the page buffer. */
static void slide_start(u32 dir)
{
    copy_frame(anim_new, LCD_COLS + (CTX << 9));
    ui.anim_dir = dir;
    ui.anim_frame = 0u;
}

/* Draws the next frame; 0 once the last one has been shown. */
static u32 slide_step(void)
{
    if (!ui.anim_dir)
        return 0u;
    slide_frame(ui.anim_dir, slide[ui.anim_frame]);
    if (++ui.anim_frame >= SLIDE_FRAMES) {
        ui.anim_dir = 0u;
        ui.repaint = 1u;    /* repaint the live page over the last frame */
    }
    return 1u;
}

static void tick(void)
{
    u32 ready = PORT_STATE[3] == 1u && PORT_STATE[9] != 0u;
    u32 q = TX4[5], last = ui.last, usb, knobs, hold;
    ui.stall = ready && q ? ui.stall + (ui.stall < STALL_TICKS) : 0u;
    usb = !ready ? 0u : ui.stall >= STALL_TICKS ? 2u : 1u;
#ifdef CTL_DIAG
    ui.repaint = 1u;                   /* the tick counter changes every time */
#endif
    knobs = (u32)ctl_state.knob[0] | (u32)ctl_state.knob[1] << 8 |
            (u32)ctl_state.knob[2] << 16 | (u32)ctl_state.knob[3] << 24;
    hold = controller_hold_ticks() >= HOLD_TICKS;
    if (!ui.repaint && ui.anim_req != ANIM_ENTER && ui.shown[0] == usb && ui.shown[1] == q && ui.shown[2] == last
            && ui.shown[3] == ui.sent && ui.shown[4] == knobs && ui.shown[5] == hold)
        return;
    ui.shown[0] = usb;
    ui.shown[1] = q;
    ui.shown[2] = last;
    ui.shown[3] = ui.sent;
    ui.shown[4] = knobs;
    ui.shown[5] = hold;
    ui.repaint = 0u;
    if (ui.anim_req == ANIM_ENTER) {
        /* The buffer still holds the stock screen: it is the old frame. */
        ui.anim_req = 0u;
        copy_frame(anim_old, LCD_COLS + (CTX << 9));
        compose(usb, q, last, hold);
        slide_start(ANIM_ENTER);
        slide_step();
        return;
    }
    compose(usb, q, last, hold);
    flush();
}

/* An infinite wait is replaced by finite waits that return only on a real
   event: the same contract for the caller in either mode. This also covers a
   wait that began before controller_start latched the mode. */
u32 controller_ui_pend(u32 event, u32 and_mask, u32 or_mask, int timeout)
{
    u32 r;
    if (timeout != -1)
        return STOCK_PEND(event, and_mask, or_mask, timeout);
    if (ui.anim_req == ANIM_LEAVE && !ctl_state.mode) {
        /* Stock has just redrawn its screen (event bit 0 below): slide it in
           over the saved MIDI page before the first wait. */
        ui.anim_req = 0u;
        slide_start(ANIM_LEAVE);
        slide_step();
    }
    for (;;) {
        r = STOCK_PEND(event, and_mask, or_mask, ui.anim_dir ? ANIM_TICKS : UI_TICKS);
        if (r) {
            ui.repaint = 1u;
            return r;
        }
        if (slide_step())
            continue;
        if (ctl_state.mode) {
            tick();
        } else if (ui.stock_redraw) {
            ui.stock_redraw = 0u;
            ui.anim_req = ANIM_LEAVE;
            copy_frame(anim_old, LCD_COLS + (CTX << 9));   /* the MIDI page */
            return 1u;
        }
#ifdef CTL_CF_HEADER
        else {
            cf_header_tick();          /* CPU meter on the edit page (cf_header.c) */
        }
#endif
    }
}

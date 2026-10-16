/* Host-only harness for controller_ui.c. Never compile/link this into the pedal.
   The stock LCD, gate and wait routines are replaced by recorders; the tests
   render the recorded draw calls with the firmware's own fonts (tools/ui_mock.py).
   No C runtime is used. */
#ifdef _MSC_VER
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
#define UI_HOST

typedef unsigned int hu32;

/* draw-call record: op 1 clear, 2 glyph5 (ch, page, x), 3 text8 (x, y, str) */
#define MAXOPS 256
EXPORT hu32 host_op[MAXOPS], host_a[MAXOPS], host_b[MAXOPS], host_c[MAXOPS];
EXPORT char host_str[MAXOPS][32];
EXPORT hu32 host_nops, host_flushes, host_gate_depth, host_gate_bad;
EXPORT hu32 host_port[16], host_tx4[16], host_ticks, host_pend_results[8], host_pend_count;
EXPORT unsigned char host_dirty[4], host_lcd[512];
EXPORT hu32 host_hold;
EXPORT hu32 host_diag[4] = { 768, 2, 0, 1 };   /* peak, creates, fault, teardown */

static void rec(hu32 op, hu32 a, hu32 b, hu32 c, const char *s)
{
    hu32 i = 0;
    if (host_nops >= MAXOPS)
        return;
    host_op[host_nops] = op;
    host_a[host_nops] = a;
    host_b[host_nops] = b;
    host_c[host_nops] = c;
    if (s)
        for (; s[i] && i < 31u; i++)
            host_str[host_nops][i] = s[i];
    host_str[host_nops][i] = 0;
    host_nops++;
}

static hu32 h_pend(hu32 e, hu32 am, hu32 om, int t)
{
    (void)e; (void)am; (void)om; (void)t;
    return host_pend_count < 8u ? host_pend_results[host_pend_count++] : 1u;
}
static void h_clear(hu32 ctx, hu32 f) { (void)f; rec(1, ctx, 0, 0, 0); }
static void h_glyph(hu32 ctx, hu32 ch, hu32 page, hu32 x) { (void)ctx; rec(2, ch, page, x, 0); }
static void h_text(hu32 ctx, const char *s, hu32 x, hu32 y) { (void)ctx; rec(3, x, y, 0, s); }
static hu32 h_enter(hu32 gate) { (void)gate; host_gate_depth++; return 0x55u; }
static void h_flush(hu32 ctx) { (void)ctx; if (host_gate_depth != 1u) host_gate_bad++; host_flushes++; }
static void h_leave(hu32 gate, hu32 key) { (void)gate; if (key != 0x55u) host_gate_bad++; host_gate_depth--; }

#define STOCK_PEND h_pend
#define LCD_CLEAR h_clear
#define GLYPH5 h_glyph
#define TEXT8 h_text
#define GATE_ENTER h_enter
#define LCD_FLUSH h_flush
#define GATE_LEAVE h_leave
#define LCD_GATE 0u
#define LCD_DIRTY host_dirty
#define PORT_STATE host_port
#define TX4 host_tx4
#define TICKS host_ticks
#define LCD_COLS host_lcd

#ifdef CTL_DIAG
void controller_diag_ui(hu32 *peak, hu32 *creates, hu32 *fault, hu32 *teardown)
{
    *peak = host_diag[0];
    *creates = host_diag[1];
    *fault = host_diag[2];
    *teardown = host_diag[3];
}
#endif

#ifdef CTL_DIAG
EXPORT hu32 host_beacons = 7;
hu32 controller_diag_beacons(void) { return host_beacons; }
#endif

hu32 controller_hold_ticks(void) { return host_hold; }

#include "controller_ui.c"

State ctl_state;

EXPORT void host_reset(void)
{
    hu32 i;
    host_nops = host_flushes = host_gate_depth = host_gate_bad = host_pend_count = 0;
    for (i = 0; i < 4u; i++)
        host_dirty[i] = 0;
    for (i = 0; i < 512u; i++)
        host_lcd[i] = 0;
    ui.anim_req = ui.anim_dir = ui.anim_frame = 0u;
}
EXPORT void host_knob(hu32 i, hu32 v) { ctl_state.knob[i] = (unsigned char)v; }
EXPORT void host_set_mode(hu32 m) { ctl_state.mode = (unsigned char)m; }
EXPORT void host_tick(void) { tick(); }
EXPORT hu32 host_pend(int timeout) { return controller_ui_pend(1, 0, 255, timeout); }
EXPORT void host_sent(hu32 c, hu32 v) { controller_ui_sent(c, v); }
EXPORT hu32 host_repaint(void) { return ui.repaint; }
EXPORT void host_ui_mode(hu32 m) { controller_ui_mode(m); }
EXPORT hu32 host_anim_dir(void) { return ui.anim_dir; }
EXPORT hu32 host_anim_req(void) { return ui.anim_req; }
/* Geometry check: old frame = column number, new frame = 0x80 | column. */
EXPORT void host_slide_frame(hu32 dir, hu32 n)
{
    hu32 i;
    for (i = 0; i < 512u; i++) {
        anim_old[i] = (unsigned char)(i & 127u);
        anim_new[i] = (unsigned char)(0x80u | (i & 127u));
    }
    slide_frame(dir, n);
}

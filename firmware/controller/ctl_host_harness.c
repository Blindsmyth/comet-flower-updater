/* Host-only harness for controller.c's event and mode logic. Never compile or
   link this into the pedal. Stock calls are replaced by recorders; see
   tests/test_controller_mode.py. No C runtime is used. */
#ifdef _MSC_VER
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
#define CTL_HOST
#define CTL_UI

typedef unsigned int hu32;

EXPORT hu32 host_ticks, host_mbx = 0x1234u, host_last_raw, host_switches = ~0u;
EXPORT hu32 host_posts, host_post_msg[4], host_post_ok = 1, host_post_handle;
EXPORT hu32 host_ui_modes[8], host_ui_nmodes, host_port[16], host_lock;
EXPORT hu32 host_ring[1027];

static void h_startup(void) {}
static void h_switches(hu32 *bits) { *bits = host_switches; }
static void h_analog(hu32 v) { (void)v; }
static int h_event_post(hu32 e, hu32 b) { (void)e; (void)b; return 0; }
static int h_pend(hu32 l) { (void)l; return 0; }
static int h_post(hu32 l) { (void)l; return 0; }
static int h_append(volatile hu32 *ring, hu32 byte)
{
    hu32 w = ring[1];
    ring[2 + w] = byte;
    ring[1] = w + 1u >= 1025u ? 0u : w + 1u;
    return 0;
}
static hu32 h_create(hu32 d) { return d; }
static int h_mbx_post(hu32 handle, void *msg, int timeout)
{
    hu32 i;
    (void)timeout;
    host_post_handle = handle;
    for (i = 0; i < 4u; i++)
        host_post_msg[i] = ((hu32 *)msg)[i];
    host_posts++;
    return (int)host_post_ok;
}

#define STOCK_STARTUP h_startup
#define READ_SWITCHES h_switches
#define STOCK_ANALOG h_analog
#define EVENT_POST h_event_post
#define INNER_PEND h_pend
#define INNER_POST h_post
#define RING_APPEND h_append
#define TASK_CREATE h_create
#define MIDI_LOCK host_lock
#define PORT_STATE host_port
#define TICKS host_ticks
#define MAINAPP_MBX host_mbx
#define MBX_POST h_mbx_post
#define LAST_RAW_ID host_last_raw
#define RING host_ring

void controller_ui_sent(hu32 control, hu32 value) { (void)control; (void)value; }
void controller_ui_mode(hu32 mode)
{
    if (host_ui_nmodes < 8u)
        host_ui_modes[host_ui_nmodes++] = mode;
}

EXPORT hu32 host_menu_installs;
hu32 controller_menu_install(void) { host_menu_installs++; return 1u; }

#include "controller.c"

EXPORT void host_set_mode_from_menu(hu32 mode) { controller_set_mode(mode); }
EXPORT hu32 host_get_mode_for_menu(void) { return controller_get_mode(); }

EXPORT hu32 host_mode(void) { return ctl_state.mode; }
EXPORT hu32 host_knob_record(hu32 i) { return tx.knob_record[i]; }
EXPORT hu32 host_connected(void) { return tx.connected; }
EXPORT void host_set_connected(hu32 c) { tx.connected = c; }
EXPORT hu32 host_edges(hu32 *out, hu32 max)
{
    hu32 n = 0, h = tx.btn_head;
    while (h != tx.btn_tail && n < max) {
        out[n++] = tx.btn_edge[h];
        h = (h + 1u) & (BTN_QLEN - 1u);
    }
    return n;
}
/* What the dispatch hook does with one normalized record: 0 stock, 1 consumed,
   2 controller_event. */
EXPORT hu32 host_dispatch(int *event)
{
    if (ctl_state.mode) {
        controller_event(event);
        return 2u;
    }
    return controller_gate(event) ? 1u : 0u;
}
EXPORT void host_start(void) { controller_start(); }

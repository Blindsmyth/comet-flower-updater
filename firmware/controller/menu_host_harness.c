/* Host-only harness for controller_menu.c. Never compile/link this into the pedal.
   The stock descriptor tables are host arrays holding their boot contents
   (decoded from the .cinit data), and the stock screen, draw and editor
   routines are recorders. No C runtime is used. */
#ifdef _MSC_VER
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
#define UI_HOST

typedef unsigned int hu32;
typedef unsigned long long hword;

EXPORT hword host_desc0[9], host_desc1[9], host_desc5[9], host_list_b[5];
EXPORT hu32 host_col_x[4] = { 17, 48, 79, 110 };
EXPORT hu32 host_screen, host_set_calls, host_set_last;
EXPORT hu32 host_chooser_calls, host_edit_calls, host_edit_count, host_draw_calls;
EXPORT hu32 host_draw_count, host_draw_font_label, host_draw_font_value;
EXPORT const char *host_draw_title;
EXPORT const hword *host_draw_records;
EXPORT hu32 host_mode, host_mode_sets;
EXPORT hu32 host_ua[8], host_usb_state, host_closes, host_opens, host_slept;
EXPORT unsigned char host_usb_ready;
EXPORT hu32 host_trace[8], host_ntrace;   /* 1 close, 2 sleep, 3 open */

static void h_set(hu32 id) { host_set_calls++; host_set_last = id; host_screen = id; }
static hu32 h_id(void) { return host_screen; }
static void h_draw(hu32 n, const hword *r, const hu32 *x, const char *t, hu32 a, hu32 b)
{
    (void)x;
    host_draw_calls++;
    host_draw_count = n;
    host_draw_records = r;
    host_draw_title = t;
    host_draw_font_label = a;
    host_draw_font_value = b;
}
static int h_edit(hu32 n, int *ev, const hword *r)
{
    (void)ev;
    (void)r;
    host_edit_calls++;
    host_edit_count = n;
    return 1;
}
static int h_chooser(int *ev) { (void)ev; host_chooser_calls++; return 7; }
static void h_trace(hu32 k) { if (host_ntrace < 8u) host_trace[host_ntrace++] = k; }
static void h_close(void) { host_closes++; h_trace(1u); }
static void h_open(void) { host_opens++; h_trace(3u); }
static void h_sleep(hu32 ms) { host_slept = ms; h_trace(2u); }
EXPORT hu32 host_switch_task = 0x5a5au;
EXPORT int host_pris[8];
static void h_setpri(hu32 task, int pri) { if (task == 0x5a5au) h_trace(pri < 0 ? 4u : 5u); host_pris[host_ntrace & 7u] = pri; }

#define SCREEN_SET h_set
#define SCREEN_ID h_id
#define PAGE_DRAW h_draw
#define ITEM_EDIT h_edit
#define CHOOSER_EVENT h_chooser
#define DESC0 host_desc0
#define DESC1 host_desc1
#define DESC5 host_desc5
#define LIST_B host_list_b
#define COL_X host_col_x
#define UA host_ua
#define USB_STATE host_usb_state
#define USB_READY host_usb_ready
#define USB_CLOSE h_close
#define USB_OPEN h_open
#define SLEEP_MS h_sleep
#define TASK_SETPRI h_setpri
#define SWITCH_TASK host_switch_task

hu32 controller_get_mode(void) { return host_mode; }
void controller_set_mode(hu32 mode) { host_mode_sets++; host_mode = mode; }

#include "controller_menu.c"

EXPORT void host_reset(void)
{
    static const hword d0[9] = { 0, 0, 0, 0, 0, 0, 0xc0157c0c, 0xc01579c0, 0xc0157bac };
    static const hword d1[9] = { 1, 0, 0, 0, 0, 0, 0xc0157c0c, 0xc01579c0, 0xc0157bac };
    static const hword d5[9] = { 5, 0xc017ea88, 0xc017e788, 0xc017e488, 0xc016a978, 0,
                                 0xc016a97a, 0xc016a940, 0xc016a95a };
    static const hword lb[5] = { 5, 9, 3, 8, 12 };
    hu32 i;
    for (i = 0; i < 9u; i++) {
        host_desc0[i] = d0[i];
        host_desc1[i] = d1[i];
        host_desc5[i] = d5[i];
    }
    for (i = 0; i < 5u; i++)
        host_list_b[i] = lb[i];
    host_screen = 0;
    host_set_calls = host_set_last = host_chooser_calls = host_edit_calls = 0;
    host_edit_count = host_draw_calls = host_draw_count = 0;
    host_mode = host_mode_sets = 0;
    for (i = 0; i < 8u; i++)
        host_ua[i] = 0;
    host_usb_state = 1;
    host_usb_ready = 0;
    host_closes = host_opens = host_slept = host_ntrace = 0;
}

EXPORT hu32 host_install(void) { return controller_menu_install(); }

EXPORT hword host_icon(hu32 k)
{
    if (k == 0u)
        return (hword)menu_icon_small;
    return k == 1u ? (hword)menu_icon_medium : (hword)menu_icon_large;
}

/* Calls an installed event callback the way the stock dispatcher does. */
EXPORT int host_event(hword *desc, int id, int w2)
{
    int ev[4];
    ev[0] = id;
    ev[1] = 0;
    ev[2] = w2;
    ev[3] = 1;
    return ((int (*)(int *))desc[8])(ev);
}

EXPORT void host_page_draw(void) { ((void (*)(hu32))host_desc5[6])(1u); }

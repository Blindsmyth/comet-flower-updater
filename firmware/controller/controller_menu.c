/* Comet Flower settings page in Zoom's SETTING menu (owner request 2026-10-16).
 *
 * Owner decisions: no stock menu item is given up; our page lives on a second
 * chooser page and must leave room for more pages and settings; turning a knob
 * on the SETTING chooser flips between the two chooser pages; the pedal
 * always boots in FX mode (nothing is persisted).
 *
 * Recon: docs/helpers/MENU_RE_{ASTRA,ARGON}_2026-10-16.md and
 * MENU_PAGES_ARGON_2026-10-16.md; every address below re-checked by Claude in
 * main.dis (docs/CF_MENU_PAGE_2026-10-16.md lists the evidence).
 *
 * Screen descriptors are 9 words {id, icon small, medium, large, enter, exit,
 * draw, poll, event} in .cinit-initialized RAM, so they are rewritten here
 * once, from controller_start (MainApp start-up, after the C auto-init):
 *   ID 0 c01833dc  chooser, list A c0181350 {4,6,7,10,11}  event c0157bac
 *   ID 1 c0183400  chooser, list B c0181368 {5,9,3,8,12}   event c0157bac
 *                  (no stock path ever selects ID 1)
 *   ID 5 c0183740  OUTPUT 4-knob page, only listed in B  draw c016a97a event c016a95a
 * Our chooser event flips 0 <-> 1 on a knob turn (events 25..28, signed
 * delta in word 2; c0157bac ignores ids outside 6..20). List B keeps ID 5 in
 * slot 0, now our page; slots 1..4 point at ID 1, whose icon words are 0 so
 * the chooser draws nothing there (c0157a10), and their slot events (12, 14,
 * 16, 18, 20 with the slot in word 2, as c0157ae8 reads it) are swallowed.
 * The page draws with the stock 4-knob page builder c0154564 and edits with
 * the stock item editor c0149948 (index = event - 25 < count; getter word 8,
 * clamp to words 5..6, setter word 9, after-change word 10; returns 1 when
 * the value changed).
 * Every table is checked against its stock contents first: on any mismatch
 * nothing is changed and the menu stays stock.
 * No division and no switch: the payload has no run-time support library.
 */
typedef unsigned int u32;
#ifdef UI_HOST
typedef unsigned long long word;   /* a table word holds a pointer on the host */
#else
typedef u32 word;
#endif

#include "menu_icon.h"

#ifndef UI_HOST   /* tests/test_controller_menu.py supplies host tables */
#define SCREEN_SET ((void (*)(u32))0xc0149664u)
#define SCREEN_ID ((u32 (*)(void))0xc01497f4u)
#define PAGE_DRAW ((void (*)(u32, const word *, const u32 *, const char *, u32, u32))0xc0154564u)
#define ITEM_EDIT ((int (*)(u32, int *, const word *))0xc0149948u)
#define CHOOSER_EVENT ((int (*)(int *))0xc0157bacu)
#define DESC0 ((volatile word *)0xc01833dcu)
#define DESC1 ((volatile word *)0xc0183400u)
#define DESC5 ((volatile word *)0xc0183740u)
#define LIST_B ((volatile word *)0xc0181368u)
#define COL_X ((const u32 *)0xc0181548u)   /* column centres {17, 48, 79, 110} */
/* USB-audio layer (firmware/usb_audio/ua_glue.c): {active, request, magic} */
#define UA ((volatile u32 *)0xc01a8000u)
/* Stock USB lifecycle, as the cable handler 1180a7ec uses it: state word 0
   = USB open (attach writes 0 after c016ab8c, detach 1 after c016ab58);
   118134a0 = USB layer initialised (its gate at 1180a800). */
#define USB_STATE (*(volatile u32 *)0x1181349cu)
#define USB_READY (*(volatile unsigned char *)0x118134a0u)
#define USB_CLOSE ((void (*)(void))0xc016ab58u)    /* worker + MIDI + controller close */
#define USB_OPEN ((void (*)(void))0xc016ab8cu)     /* full init + MIDI open + connect */
#define SLEEP_MS ((void (*)(u32))0xc014a28cu)      /* c0158980 Task_sleep, 1 tick = 1 ms */
/* The cable handler 1180a7ec runs in the switch task (SwitchNrmlSpdRead,
   priority 9 > MainApp 3) and calls the same unlocked close/open. Stock sets
   its priority with Task_setPri c01529c0(*B14[156], 9) (c0157138..44);
   MIDI teardown uses the same call with -1 (c0159644) to park a task. */
#define TASK_SETPRI ((void (*)(u32, int))0xc01529c0u)
#define SWITCH_TASK (*(volatile u32 *)0xc0185070u)  /* B14[156], B14 = c0184e00 */
#endif
#define SWITCH_TASK_PRI 9
#define UA_MAGIC 0x41425355u                       /* "USBA" */
#define REPLUG_MS 500u                             /* detached time the host sees */

#define STOCK_CHOOSER_EVENT 0xc0157bacu
#define STOCK_OUTPUT_DRAW 0xc016a97au
#define STOCK_OUTPUT_EVENT 0xc016a95au

u32 controller_get_mode(void);        /* controller.c */
void controller_set_mode(u32 mode);

/* ---- the Comet Flower page ------------------------------------------- */

static const char *mode_text(int value)
{
    return value ? "MIDI" : "FX";
}

static int mode_get(void)
{
    return (int)controller_get_mode();
}

static void mode_set(int value)
{
    controller_set_mode(value ? 1u : 0u);
}

/* USB AUDIO: shown only when the USB-audio layer is in the image. The value
   is the request; it takes effect at the next USB open. Changing it while
   USB is open replugs in software with the same stock close/open the cable
   handler runs (EXPERIMENTAL: docs/CF_USB_MODE_2026-10-16.md; Astra's
   finding 6: in-flight transfer recovery on a live close is unproved). This
   runs in MainApp's event dispatch, like the boot-time open (c0134354 ->
   c016c150 -> c016ab8c), and blocks it for the close, REPLUG_MS and the open. */
static u32 ua_present(void)
{
    return UA[2] == UA_MAGIC;
}

static const char *usb_text(int value)
{
    return value ? "AUDIO" : "OFF";
}

static int usb_get(void)
{
    return UA[1] ? 1 : 0;
}

/* The switch task is parked (priority -1) for the replug so a cable event
   cannot run the same close/open in the middle of ours (review
   USB_MODE_REVIEW_ASTRA_2026-10-16.md R3); the USB state is checked again
   after parking. Once restored, the task compares the cable pin with its
   state word on its next poll, so a cable change in the window is handled
   then. The task also scans the buttons: they pause for the window. */
static void usb_set(int value)
{
    UA[1] = value ? 1u : 0u;
    if (UA[0] == UA[1] || !USB_READY || USB_STATE != 0u)
        return;
    TASK_SETPRI(SWITCH_TASK, -1);
    if (USB_STATE == 0u) {
        USB_CLOSE();
        SLEEP_MS(REPLUG_MS);
        USB_OPEN();
    }
    TASK_SETPRI(SWITCH_TASK, SWITCH_TASK_PRI);
}

/* One 0x2c record per knob: {index, 0xfff, 0xfff, label, label line 2, min,
   max, formatter, getter, setter, after-change}. */
#define CF_ITEMS_MAX 2u
static const word cf_items[CF_ITEMS_MAX * 11u] = {
    0u, 0xfffu, 0xfffu, (word)"MODE", 0u, 0u, 1u,
    (word)mode_text, (word)mode_get, (word)mode_set, 0u,
    1u, 0xfffu, 0xfffu, (word)"USB", 0u, 0u, 1u,
    (word)usb_text, (word)usb_get, (word)usb_set, 0u,
};

static u32 cf_count(void)
{
    return ua_present() ? 2u : 1u;
}

static void cf_page_draw(u32 flag)
{
    (void)flag;
    PAGE_DRAW(cf_count(), cf_items, COL_X, "COMET FLOWER", 1u, 1u);
}

static int cf_page_event(int *event)
{
    int id = event[0];
    u32 n = cf_count();
    if (id < 25 || id >= 25 + (int)n)
        return 0;
    return ITEM_EDIT(n, event, cf_items);
}

/* ---- chooser ---------------------------------------------------------- */

static int cf_chooser_event(int *event)
{
    int id = event[0];
    u32 page = SCREEN_ID();
    if (id >= 25 && id <= 28) {
        u32 want = event[2] > 0 ? 1u : 0u;
        if (event[2] == 0 || want == page)
            return 0;
        SCREEN_SET(want);
        return 1;
    }
    if (page == 1u && id >= 12 && id <= 20 && !(id & 1) && event[2] != 0)
        return 0;                       /* an empty slot on page 2 */
    return CHOOSER_EVENT(event);
}

/* ---- install ---------------------------------------------------------- */

static const word stock_list_b[5] = { 5u, 9u, 3u, 8u, 12u };

/* Returns 1 when installed, 0 when a table did not hold its stock contents. */
u32 controller_menu_install(void)
{
    u32 i;
    if (DESC0[0] != 0u || DESC0[8] != STOCK_CHOOSER_EVENT ||
        DESC1[0] != 1u || DESC1[8] != STOCK_CHOOSER_EVENT ||
        DESC1[1] != 0u || DESC1[2] != 0u || DESC1[3] != 0u ||
        DESC5[0] != 5u || DESC5[6] != STOCK_OUTPUT_DRAW || DESC5[8] != STOCK_OUTPUT_EVENT)
        return 0u;
    for (i = 0; i < 5u; i++)
        if (LIST_B[i] != stock_list_b[i])
            return 0u;
    DESC5[1] = (word)menu_icon_small;
    DESC5[2] = (word)menu_icon_medium;
    DESC5[3] = (word)menu_icon_large;
    DESC5[6] = (word)cf_page_draw;
    DESC5[8] = (word)cf_page_event;
    for (i = 1; i < 5u; i++)
        LIST_B[i] = 1u;
    DESC1[8] = (word)cf_chooser_event;
    DESC0[8] = (word)cf_chooser_event;
    return 1u;
}

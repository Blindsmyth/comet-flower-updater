/* Comet Flower start-up animation (make_controller_fw.py --boot-anim; TEST builds, needs --ui).
 *
 * The start-up screen (c014dc08) draws the 92x16 logo through c014db64:
 *   c014db78 CALLP c011c508(ctx A4, x B4 = 18, y A6 = 8, w B6 = 92, h A8 = 16, buf B8 = c017bf38)
 * That one CALLP comes here. The first time after power-on (ctx 0) the stock
 * logo is drawn as before and then the whole 128x32 page buffer is replaced by
 * frame 0 of the bloom; UpdateUI's own flush follows. A redraw of the screen
 * while the animation runs puts the current frame back. Every later UpdateUI idle
 * wake-up (controller_ui_pend -> cf_boot_tick, ~UI_TICKS) shows the next frame
 * while our last frame is still in the buffer; once the stock code draws the
 * next screen, or after the last frame (held), it stops for good. Any other
 * call (a later visit of the same screen) is the stock draw, unchanged.
 * The boot program's own ZOOM logo (flash 0x0..0x28000) comes before and is
 * not touched (recon/25: never write the boot region).
 *
 * Frames: boot_anim.h (tools/make_boot_anim.py), LCD page format run-length
 * coded: t < 0x80 -> t + 1 literal bytes, t >= 0x80 -> (t & 0x7f) + 1 zeros.
 * No division, no switch, no initialised writable data.
 */
typedef unsigned int u32;
typedef unsigned char u8;

#include "boot_anim.h"

#ifndef CFB_HOST
#define STOCK_BLIT ((u32 (*)(u32, u32, u32, u32, u32, u32))0xc011c508u)
#define LCD_COLS ((volatile u8 *)0x11800000u)
#define LCD_DIRTY ((volatile u8 *)0x11813250u)
#define GATE_ENTER ((u32 (*)(u32))0xc0161200u)
#define LCD_FLUSH ((void (*)(u32))0xc016df00u)
#define GATE_LEAVE ((void (*)(u32, u32))0xc016d880u)
#define LCD_GATE (*(volatile u32 *)0xc0185054u)        /* B14[149] */
#endif

#define BOOT_IDLE 0u
#define BOOT_RUN 1u
#define BOOT_DONE 2u

static u8 boot_frame[512];
static u32 boot_state, boot_n;

static void decode(u32 n)
{
    const u8 *p = boot_rle + boot_off[n];
    u32 i = 0, k, t;
    while (i < 512u) {
        t = *p++;
        if (t & 0x80u) {
            for (k = (t & 0x7fu) + 1u; k && i < 512u; k--)
                boot_frame[i++] = 0u;
        } else {
            for (k = t + 1u; k && i < 512u; k--)
                boot_frame[i++] = *p++;
        }
    }
}

static void show(void)
{
    u32 i;
    for (i = 0; i < 512u; i++)
        LCD_COLS[i] = boot_frame[i];
    LCD_DIRTY[0] |= 0x0fu;
}

/* Our frame is still on screen: at most BOOT_SLACK bytes differ (a small stock
   touch-up does not end the animation; the next screen differs in far more). */
#define BOOT_SLACK 32u
static u32 still_shown(void)
{
    u32 i, d = 0;
    for (i = 0; i < 512u; i++)
        if (LCD_COLS[i] != boot_frame[i] && ++d > BOOT_SLACK)
            return 0u;
    return 1u;
}

u32 cf_boot_logo(u32 ctx, u32 x, u32 y, u32 w, u32 h, u32 buf)
{
    u32 r = STOCK_BLIT(ctx, x, y, w, h, buf);
    if (ctx != 0u || boot_state == BOOT_DONE)
        return r;
    if (boot_state == BOOT_IDLE) {
        boot_state = BOOT_RUN;
        boot_n = 0u;
        decode(0u);
    }
    show();                       /* first draw, or a redraw of the start-up screen mid-animation */
    return r;
}

/* UpdateUI idle wake-up (controller_ui_pend). Returns 1 if it drew. */
u32 cf_boot_tick(void)
{
    u32 key;
    if (boot_state != BOOT_RUN)
        return 0u;
    if (!still_shown() || boot_n + 1u >= BOOT_NFRAMES) {
        boot_state = BOOT_DONE;
        return 0u;
    }
    decode(++boot_n);
    show();
    key = GATE_ENTER(LCD_GATE);
    LCD_FLUSH(0);
    GATE_LEAVE(LCD_GATE, key);
    return 1u;
}

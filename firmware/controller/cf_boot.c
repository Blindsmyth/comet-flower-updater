/* Comet Flower start-up bloom (make_controller_fw.py --boot-anim; TEST builds).
 *
 * The start-up screen (c014dc08) draws the 92x16 logo through c014db64:
 *   c014db78 CALLP c011c508(ctx A4, x B4 = 18, y A6 = 8, w B6 = 92, h A8 = 16, buf B8 = c017bf38)
 * That one CALLP comes here. The first time after power-on (ctx 0) the stock
 * logo is drawn as before and then the bloom plays in place, frames
 * BOOT_FIRST..BOOT_NFRAMES-1 over the whole 128x32 screen, each flushed and
 * held FRAME_CYCLES of the CPU cycle counter; the last frame stays in the
 * buffer for UpdateUI's own flush. Any later call is the stock draw.
 *
 * Why timed here and not on UI ticks: 0.34.4/0.34.5 advanced one frame per
 * UpdateUI idle wake-up, and on the pedal it never got one while the logo
 * screen showed (frame 0 stayed). So the bloom runs inside this call, in
 * UpdateUI's task, before the stock render continues (~0.8 s added to boot).
 * The gate B14[149] is not held here: c014dc08 enters it only after c014db64
 * (c014db8c), and UpdateUI flushes after the render (c013c72c..c013c748).
 *
 * The boot program draws its own logo before the main firmware starts; with
 * tools/make_boot_logo_updater.py it shows frame BOOT_FIRST's bud cropped to
 * the logo box, so the bloom appears to continue from it.
 *
 * Cycle counter: TSCL, started by stock; if it is not counting yet, a write
 * starts it. Every wait is also capped by an iteration count, so a stopped
 * counter cannot hang the start-up.
 * Frames: boot_anim.h (tools/make_boot_anim.py), LCD page format run-length
 * coded: t < 0x80 -> t + 1 literal bytes, t >= 0x80 -> (t & 0x7f) + 1 zeros.
 * No division, no switch, no initialised writable data.
 */
typedef unsigned int u32;
typedef unsigned char u8;

#include "boot_anim.h"

#ifndef CFB_HOST
extern __cregister volatile unsigned int TSCL;
#define NOW() TSCL
#define START_CLOCK() (TSCL = 0u)
#define STOCK_BLIT ((u32 (*)(u32, u32, u32, u32, u32, u32))0xc011c508u)
#define LCD_COLS ((volatile u8 *)0x11800000u)
#define LCD_DIRTY ((volatile u8 *)0x11813250u)
#define GATE_ENTER ((u32 (*)(u32))0xc0161200u)
#define LCD_FLUSH ((void (*)(u32))0xc016df00u)
#define GATE_LEAVE ((void (*)(u32, u32))0xc016d880u)
#define LCD_GATE (*(volatile u32 *)0xc0185054u)        /* B14[149] */
#endif

#ifndef BOOT_FIRST
#define BOOT_FIRST 4u                 /* the bud: the boot program's logo shows this frame */
#endif
#define FRAME_CYCLES (364800u * 70u)  /* 70 ms at 364.8 MHz */
#ifndef WAIT_CAP
#define WAIT_CAP 2000000u             /* loop passes per frame at most: a stopped counter costs ~10 ms a frame */
#endif

static u8 boot_frame[512];
static u32 boot_done;

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

static void flush(void)
{
    u32 key = GATE_ENTER(LCD_GATE);
    LCD_FLUSH(0);
    GATE_LEAVE(LCD_GATE, key);
}

static void wait_frame(void)
{
    u32 t0 = NOW(), n = 0;
    while ((u32)(NOW() - t0) < FRAME_CYCLES && ++n < WAIT_CAP)
        ;
}

u32 cf_boot_logo(u32 ctx, u32 x, u32 y, u32 w, u32 h, u32 buf)
{
    u32 r = STOCK_BLIT(ctx, x, y, w, h, buf), f;
    if (ctx != 0u || boot_done)
        return r;
    boot_done = 1u;
    if (NOW() == NOW())
        START_CLOCK();
    for (f = BOOT_FIRST; f < BOOT_NFRAMES; f++) {
        decode(f);
        show();
        if (f + 1u < BOOT_NFRAMES) {   /* the last frame goes out with UpdateUI's own flush */
            flush();
            wait_frame();
        }
    }
    return r;
}

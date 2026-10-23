/* Host-only harness for cf_boot.c (tests/test_cf_boot.py). Never link into the pedal.
   The LCD is a host array, the stock blitter a recorder, the cycle counter a host
   variable that advances host_step per read (0 = a stopped counter). */
#ifdef _MSC_VER
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
#define CFB_HOST

EXPORT unsigned char host_lcd[512], host_dirty[2];
EXPORT unsigned int host_blits, host_flushes, host_clock, host_step = 1000000u, host_starts;
EXPORT unsigned char host_seen[16][512];          /* the buffer at each flush */
static unsigned int h_enter(unsigned int g) { (void)g; return 1u; }
static void h_flush(unsigned int ctx)
{
    unsigned int i;
    (void)ctx;
    if (host_flushes < 16u)
        for (i = 0; i < 512u; i++)
            host_seen[host_flushes][i] = host_lcd[i];
    host_flushes++;
}
static void h_leave(unsigned int g, unsigned int k) { (void)g; (void)k; }
static unsigned int h_now(void) { host_clock += host_step; return host_clock; }

static unsigned int host_blit(unsigned int ctx, unsigned int x, unsigned int y,
                              unsigned int w, unsigned int h, unsigned int buf)
{
    unsigned int i;
    (void)y; (void)h; (void)buf;
    host_blits++;
    for (i = 0; i < w; i++)                   /* the stock logo: page 1, columns x.. */
        host_lcd[128u + x + i] = 0xA5u;
    return ctx + 0x100u;
}

#define NOW() h_now()
#define START_CLOCK() (host_starts++)
#define WAIT_CAP 1000u
#define STOCK_BLIT host_blit
#define LCD_COLS host_lcd
#define LCD_DIRTY host_dirty
#define GATE_ENTER h_enter
#define LCD_FLUSH h_flush
#define GATE_LEAVE h_leave
#define LCD_GATE 5u

#include "cf_boot.c"

EXPORT unsigned int host_logo(unsigned int ctx) { return cf_boot_logo(ctx, 18u, 8u, 92u, 16u, 0xc017bf38u); }
EXPORT unsigned int host_first(void) { return BOOT_FIRST; }
EXPORT unsigned int host_nframes(void) { return BOOT_NFRAMES; }

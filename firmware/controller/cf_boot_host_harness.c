/* Host-only harness for cf_boot.c (tests/test_cf_boot.py). Never link into the pedal.
   The LCD is a host array; the stock blitter is a recorder that writes a marker. */
#ifdef _MSC_VER
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
#define CFB_HOST

EXPORT unsigned char host_lcd[512], host_dirty[2];
EXPORT unsigned int host_blits, host_flushes;
static unsigned int h_enter(unsigned int g) { (void)g; return 1u; }
static void h_flush(unsigned int ctx) { (void)ctx; host_flushes++; }
static void h_leave(unsigned int g, unsigned int k) { (void)g; (void)k; }

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

#define STOCK_BLIT host_blit
#define LCD_COLS host_lcd
#define LCD_DIRTY host_dirty
#define GATE_ENTER h_enter
#define LCD_FLUSH h_flush
#define GATE_LEAVE h_leave
#define LCD_GATE 5u

#include "cf_boot.c"

EXPORT unsigned int host_logo(unsigned int ctx) { return cf_boot_logo(ctx, 18u, 8u, 92u, 16u, 0xc017bf38u); }
EXPORT unsigned int host_tick(void) { return cf_boot_tick(); }
EXPORT unsigned int host_state(void) { return boot_state; }
EXPORT unsigned int host_n(void) { return boot_n; }
EXPORT unsigned int host_nframes(void) { return BOOT_NFRAMES; }

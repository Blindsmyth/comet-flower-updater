/* Host-only harness for cf_header.c (tests/test_cf_header.py). Never link into the pedal.
   The live cells, LCD buffer and font are host arrays; the stock renderer is a recorder. */
#ifdef _MSC_VER
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
#define CFH_HOST

EXPORT unsigned int host_sel, host_page[5], host_ids[5], host_stock_calls, host_stock_args[6];
EXPORT unsigned char host_lcd[512], host_dirty[2], host_font[95 * 6];
EXPORT unsigned int host_cpu[9];          /* UaCpu: magic, seq, busy_avg, busy_peak, slot[5] */
EXPORT unsigned int host_flushes, host_gate;
static unsigned int h_enter(unsigned int g) { host_gate = g; return 77u; }
static void h_flush(unsigned int ctx) { (void)ctx; host_flushes++; }
static void h_leave(unsigned int g, unsigned int k) { (void)g; (void)k; }

static unsigned int host_stock(unsigned int a, unsigned int b, unsigned int c,
                               unsigned int d, unsigned int e, unsigned int f)
{
    host_stock_calls++;
    host_stock_args[0] = a; host_stock_args[1] = b; host_stock_args[2] = c;
    host_stock_args[3] = d; host_stock_args[4] = e; host_stock_args[5] = f;
    return 0x1234u;
}

#define STOCK_EDIT_DRAW host_stock
#define SEL_SLOT host_sel
#define PAGE_OF host_page
#define PATCH_ID(s) host_ids[s]
#define LCD_COLS host_lcd
#define LCD_DIRTY host_dirty
#define FONT5 ((const unsigned char *)host_font)
#define UA_CPU ((volatile const UaCpu *)host_cpu)
#define GATE_ENTER h_enter
#define LCD_FLUSH h_flush
#define GATE_LEAVE h_leave
#define LCD_GATE 5u

#include "cf_header.c"

EXPORT unsigned int host_edit_draw(void) { return cf_edit_draw(0, 1, 2, 3, 4, 5); }
EXPORT unsigned int host_tick(void) { return cf_header_tick(); }

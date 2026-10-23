/* CF edit-page header and CPU budget meter (make_controller_fw.py --cf-header; TEST builds).
 *
 * The stock edit page (the patch screen with 3 params + PAGE n/m) is drawn
 * by c012e5a8, called from c013c050 (UpdateUI row dispatch) and c0135b08.
 * Both CALLPs are retargeted here: the stock routine runs unchanged, then
 *  - if the selected slot holds an effect with a stage table below, the effect
 *    name box at the top is replaced by an inverted bar naming the stage of
 *    this page ("PRE>MUFF FUZZ"; "CFM PRE>MUFF FUZZ" when there is no meter);
 *  - if the audio code publishes the CPU record (make_usb_audio_fw.py
 *    --cpu-meter, docs/BUDGET_MODEL_2026-10-23.md), the top right corner shows
 *    the worst audio-block load of the last ~0.74 s as "NN%" (inverted at 95 %
 *    and above).
 * Same frame, before UpdateUI's flush, so the stock name never shows.
 * Between redraws, cf_header_tick (UpdateUI's idle wake-ups in FX mode,
 * controller_ui.c) refreshes the meter while the meter's own pixels are still
 * in the frame buffer, i.e. while the edit page is on screen; once another
 * screen has drawn over them it leaves the buffer alone until the next edit
 * page draw.
 *
 * Live cells (docs/EDIT_SCREEN_TRACE_2026-10-23.md, CF Probe 2026-10-23):
 *   c011abf4            selected slot 0..4
 *   c011acf0 + 4*slot   edit page of that slot, 0-based
 *   1181159c + 84*slot  effect id of that slot (in-RAM patch 0x11811598)
 * LCD page buffer ctx 0 at 11800000: byte = 8-pixel column, bit 0 on top,
 * 128 columns per 8-row page; dirty page bits at 11813250 (controller_ui.c).
 * font_5x7 at c01788a0: 6 column bytes per glyph from ' ' (recon/10).
 * No division, no switch, no initialised writable data (no .cinit).
 */
typedef unsigned int u32;
typedef unsigned char u8;

typedef struct { u32 magic, seq, busy_avg, busy_peak, slot[5]; } UaCpu;
#define CPU_MAGIC 0x4d555043u   /* "CPUM", written every block by the audio code */

#ifndef CFH_HOST
#define STOCK_EDIT_DRAW ((u32 (*)(u32, u32, u32, u32, u32, u32))0xc012e5a8u)
#define SEL_SLOT (*(volatile u32 *)0xc011abf4u)
#define PAGE_OF ((volatile u32 *)0xc011acf0u)
#define PATCH_ID(s) (*(volatile u32 *)(0x1181159cu + 84u * (s)))
#define LCD_COLS ((volatile u8 *)0x11800000u)
#define LCD_DIRTY ((volatile u8 *)0x11813250u)
#define FONT5 ((const u8 *)0xc01788a0u)
#define UA_CPU ((volatile const UaCpu *)0xc01a8020u)   /* usb_audio_tap.c ua_cpu, ua.cmd */
#define GATE_ENTER ((u32 (*)(u32))0xc0161200u)
#define LCD_FLUSH ((void (*)(u32))0xc016df00u)
#define GATE_LEAVE ((void (*)(u32, u32))0xc016d880u)
#define LCD_GATE (*(volatile u32 *)0xc0185054u)        /* B14[149] */
#endif

#define BAR_X0 19u            /* left of the bar; columns 0..17 keep the slot icon */
#define METER_X0 102u         /* meter columns 102..127 (right of the stock name box) */
#define METER_W (128u - METER_X0)
/* pct = busy * 100 / 132354 (one 16-frame block at 364.8 MHz,
   docs/CF_BENCH_RESULTS_2026-10-18.md), without a division: 3169 / 2^22. */
#define PCT_MUL 3169u
#define PCT_SHIFT 22u

typedef struct {
    u32 id;
    const char *name;     /* bar text without the meter */
    const char *tag;      /* bar text with the meter (13 characters in all) */
    u32 pages;
    const char *stage[4];
} Stages;

/* Effects whose pages are stages of one chain. Page labels in the ZD2 stay
   5 characters (the column width); the header names the stage. */
static const Stages table[] = {
    { 0x07000f91u, "CFM PRE", "PRE", 4u, { "DYNA COMP", "MUFF FUZZ", "MISTRESS", "OUTPUT" } },
};
#define NTABLE (sizeof table / sizeof table[0])

static u8 meter_sig[2 * METER_W];   /* the meter pixels last drawn (page 0, page 1 rows 8..11) */
static u32 meter_on, meter_pct;

static u32 cat(char *dst, u32 n, u32 max, const char *s)
{
    while (*s && n < max)
        dst[n++] = *s++;
    return n;
}

/* One header column, rows 0..11 (page 0 and the low nibble of page 1; rows
   12..15 belong to the labels and are kept). The glyph column g (bit 0 = top
   of the 7-row glyph) sits at rows 2..8. inv: rows 1..9 lit and the glyph cut
   out; otherwise the glyph lit on dark. */
static void column(u32 x, u32 g, u32 inv)
{
    volatile u8 *p0 = LCD_COLS + x, *p1 = LCD_COLS + 128u + x;
    u32 bits = g << 2;
    if (inv) {
        *p0 = (u8)(0xfeu & ~bits);
        *p1 = (u8)((*p1 & 0xf0u) | (0x03u & ~(bits >> 8)));
    } else {
        *p0 = (u8)(bits & 0xffu);
        *p1 = (u8)((*p1 & 0xf0u) | ((bits >> 8) & 0x03u));
    }
}

/* Text n characters wide, centred in columns x0..x1-1 (x1 - x0 >= 6n). */
static void text_box(u32 x0, u32 x1, const char *text, u32 n, u32 inv)
{
    u32 i, x, left = x0 + ((x1 - x0 - 6u * n) >> 1);
    for (x = x0; x < x1; x++)
        column(x, 0, inv);
    for (i = 0; i < n; i++) {
        const u8 *g = FONT5 + 6u * (u32)((u8)text[i] - 0x20u);
        for (x = 0; x < 6u; x++)
            column(left + 6u * i + x, g[x], inv);
    }
}

static u32 cpu_live(void)
{
    return UA_CPU->magic == CPU_MAGIC;
}

static u32 cpu_pct(void)
{
    u32 p = (UA_CPU->busy_peak * PCT_MUL + (1u << (PCT_SHIFT - 1u))) >> PCT_SHIFT;   /* rounded */
    return p > 999u ? 999u : p;
}

static void draw_meter(u32 pct)
{
    char t[4];
    u32 n = 0, x, h = 0, d = pct;
    while (d >= 100u) { d -= 100u; h++; }
    if (h)
        t[n++] = (char)('0' + h);
    x = 0;
    while (d >= 10u) { d -= 10u; x++; }
    if (h || x)
        t[n++] = (char)('0' + x);
    t[n++] = (char)('0' + d);
    t[n++] = '%';
    column(METER_X0, 0, 0);          /* one dark column: keeps an inverted meter off the bar */
    text_box(METER_X0 + 1u, 128u, t, n, pct >= 95u);
    for (x = 0; x < METER_W; x++) {
        meter_sig[x] = LCD_COLS[METER_X0 + x];
        meter_sig[METER_W + x] = (u8)(LCD_COLS[128u + METER_X0 + x] & 0x0fu);
    }
    meter_on = 1u;
    meter_pct = pct;
}

static u32 meter_still_shown(void)
{
    u32 x;
    for (x = 0; x < METER_W; x++)
        if (LCD_COLS[METER_X0 + x] != meter_sig[x]
                || (u8)(LCD_COLS[128u + METER_X0 + x] & 0x0fu) != meter_sig[METER_W + x])
            return 0u;
    return 1u;
}

void cf_header_draw(void)
{
    u32 slot = SEL_SLOT, id, page, i, n, meter = cpu_live();
    const Stages *t = 0;
    char text[18];

    if (slot <= 4u) {
        id = PATCH_ID(slot);
        for (i = 0; i < NTABLE; i++)
            if (table[i].id == id)
                t = &table[i];
    }
    if (t) {
        u32 max = meter ? 13u : 18u;
        page = PAGE_OF[slot];
        n = cat(text, 0, max, meter ? t->tag : t->name);
        if (page < t->pages) {
            n = cat(text, n, max, ">");
            n = cat(text, n, max, t->stage[page]);
        }
        text_box(BAR_X0, meter ? METER_X0 : 128u, text, n, 1u);
    }
    if (meter)
        draw_meter(cpu_pct());
    else
        meter_on = 0u;
    if (t || meter)
        LCD_DIRTY[0] |= 3u;
}

u32 cf_edit_draw(u32 a4, u32 b4, u32 a6, u32 b6, u32 a8, u32 b8)
{
    u32 r = STOCK_EDIT_DRAW(a4, b4, a6, b6, a8, b8);
    cf_header_draw();
    return r;
}

/* UpdateUI idle wake-up in FX mode (controller_ui_pend). Returns 1 if it drew. */
u32 cf_header_tick(void)
{
    u32 pct, key;
    if (!meter_on || !cpu_live())
        return 0u;
    if (!meter_still_shown()) {
        meter_on = 0u;            /* another screen: wait for the next edit page draw */
        return 0u;
    }
    pct = cpu_pct();
    if (pct == meter_pct)
        return 0u;
    draw_meter(pct);
    LCD_DIRTY[0] |= 3u;
    key = GATE_ENTER(LCD_GATE);
    LCD_FLUSH(0);
    GATE_LEAVE(LCD_GATE, key);
    return 1u;
}

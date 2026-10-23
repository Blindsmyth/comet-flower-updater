/* CF edit-page header (make_controller_fw.py --cf-header; TEST builds).
 *
 * The stock edit page (the patch screen with 3 params + PAGE n/m) is drawn
 * by c012e5a8, called from c013c050 (UpdateUI row dispatch) and c0135b08.
 * Both CALLPs are retargeted here: the stock routine runs unchanged, then,
 * if the selected slot holds an effect with a stage table below, the effect
 * name box at the top is replaced by an inverted bar reading
 * "<effect>><stage of this page>" (e.g. "CFM PRE>MUFF FUZZ"). Same frame,
 * before UpdateUI's flush, so the stock name never shows.
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

#ifndef CFH_HOST
#define STOCK_EDIT_DRAW ((u32 (*)(u32, u32, u32, u32, u32, u32))0xc012e5a8u)
#define SEL_SLOT (*(volatile u32 *)0xc011abf4u)
#define PAGE_OF ((volatile u32 *)0xc011acf0u)
#define PATCH_ID(s) (*(volatile u32 *)(0x1181159cu + 84u * (s)))
#define LCD_COLS ((volatile u8 *)0x11800000u)
#define LCD_DIRTY ((volatile u8 *)0x11813250u)
#define FONT5 ((const u8 *)0xc01788a0u)
#endif

#define BAR_X0 19u            /* left of the bar; columns 0..17 keep the slot icon */
#define BAR_W (128u - BAR_X0)
#define MAX_CHARS 18u         /* BAR_W / 6 */

typedef struct {
    u32 id;
    const char *name;
    u32 pages;
    const char *stage[4];
} Stages;

/* Effects whose pages are stages of one chain. Page labels in the ZD2 stay
   5 characters (the column width); the header names the stage. */
static const Stages table[] = {
    { 0x07000f91u, "CFM PRE", 4u, { "DYNA COMP", "MUFF FUZZ", "MISTRESS", "OUTPUT" } },
};
#define NTABLE (sizeof table / sizeof table[0])

static u32 cat(char *dst, u32 n, const char *s)
{
    while (*s && n < MAX_CHARS)
        dst[n++] = *s++;
    return n;
}

/* One header column: rows 1..9 lit, the glyph column g (bit 0 = top of the
   7-row glyph) cut out at rows 2..8; rows 0, 10, 11 dark. Rows 12..15 of
   page 1 belong to the labels and are kept. */
static void column(u32 x, u32 g)
{
    volatile u8 *p0 = LCD_COLS + x, *p1 = LCD_COLS + 128u + x;
    u32 bits = g << 2;
    *p0 = (u8)(0xfeu & ~bits);
    *p1 = (u8)((*p1 & 0xf0u) | (0x03u & ~(bits >> 8)));
}

void cf_header_draw(void)
{
    u32 slot = SEL_SLOT, id, page, i, n, x, x0;
    const Stages *t = 0;
    char text[MAX_CHARS];

    if (slot > 4u)
        return;
    id = PATCH_ID(slot);
    for (i = 0; i < NTABLE; i++)
        if (table[i].id == id)
            t = &table[i];
    if (!t)
        return;
    page = PAGE_OF[slot];
    n = cat(text, 0, t->name);
    if (page < t->pages) {
        n = cat(text, n, ">");
        n = cat(text, n, t->stage[page]);
    }
    x0 = BAR_X0 + ((BAR_W - 6u * n) >> 1);
    for (x = BAR_X0; x < 128u; x++)
        column(x, 0);
    for (i = 0; i < n; i++) {
        const u8 *g = FONT5 + 6u * (u32)((u8)text[i] - 0x20u);
        for (x = 0; x < 6u; x++)
            column(x0 + 6u * i + x, g[x]);
    }
    LCD_DIRTY[0] |= 3u;
}

u32 cf_edit_draw(u32 a4, u32 b4, u32 a6, u32 b6, u32 a8, u32 b8)
{
    u32 r = STOCK_EDIT_DRAW(a4, b4, a6, b6, a8, b8);
    cf_header_draw();
    return r;
}

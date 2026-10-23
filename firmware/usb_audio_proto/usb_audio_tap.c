/* USB audio real-audio tap (ROADMAP C3, recon/21 S1). OFFLINE candidate.
 *
 * Built INSTEAD of usb_audio.c for the tap image: it includes usb_audio.c
 * unchanged, so the silence build stays byte-identical, and adds
 *
 *   ua_tx_pack_tap          audio Swi (priority 15). Reached from the stock
 *                           CALLP at 11818c64 through a 4-word veneer at
 *                           11818c88 (dead padding after the Swi epilogue).
 *                           Runs the stock TX pack 11818aa0, then copies the
 *                           finished block into the ring.
 *   usb_audio_sof_tick_tap  SOF Hwi (CPU int 7). Replaces usb_audio_sof_tick
 *                           as the c016f770 target: one ISO packet per SOF
 *                           from the ring.
 *
 * Samples: the tap re-derives each output word from the pack's planar
 * inputs 11f038b0 (word 0 of each frame, left) and 11f038f0 (word 1, right)
 * with the pack's own math, SSHL(SMPY32(x, 0x4534fd79), 2) (11818b00..b18).
 * This avoids re-reading the EDMA PaRAM to find the written half, which can
 * pick the wrong half when the Swi finishes near its deadline. The words are
 * full-scale int32 (11818428 scales by 2^31), so the 16-bit USB sample is
 * the high half, truncated.
 *
 * Ring: single producer (Swi) / single consumer (Hwi), free-running u32
 * indices. Only the Swi writes ring_wr, only the Hwi writes ring_rd. The Hwi
 * preempts the Swi, never the reverse, so the Swi publishes ring_wr only
 * after the frames are stored (the ring is volatile so the stores stay in
 * program order).
 *
 * Clock policy: the codec (44.1 kHz from the 19.2 MHz MCLK PLL) and the host
 * SOF are independent clocks. EP1 is asynchronous (bmAttributes 0x05), so
 * the device sets the rate by its packet sizes: 45 frames when the fill is
 * above UA_TAP_TARGET, else 44. 44..45 frames/ms spans 44.0..45.0 kHz, far
 * wider than any crystal drift. Underrun: pad with zeros, count, re-prime.
 * Overrun (ring full): drop the whole block, count.
 *
 * UA_TAP_PATTERN (diagnostic build, make_usb_audio_fw.py --tap-pattern): the
 * Swi stores a known signal instead of the pedal audio, so a PC capture
 * (tools/ua_capture.py) can find every lost, repeated or damaged frame. Left
 * = a frame counter (+1 per frame, mod 2^16); right = a 1002 Hz sine,
 * ua_pattern_sine[counter mod 44], which is never 0, so an all-zero frame is
 * always padding. A block dropped on overrun still advances the counter, so
 * the drop shows as a 16-frame jump.
 *
 * The pattern build also reports the pedal's side of the link in-band: in the
 * first frame of every ring packet the right sample is replaced by a diag
 * word, (tag << 13) | (value & 0x1fff), tag = packet number mod 8:
 *   0 packets loaded >> 3   1 SOFs skipped, TxPktRdy still set
 *   2 TXCSR UnderRun seen (an IN found no packet)
 *   3 (variant << 11) | USB frames with no tick (FRAME jumped by more than 1)
 *   4 ring fill at this SOF   5 ticks that saw the same FRAME as the last one
 *   6 (tap overruns << 7) | tap underruns (6 + 7 bits)
 *   7 TXCSR as read at this SOF (low 13 bits)
 * Variants (endpoint-1 FIFO set-up, cycled every UA_VARIANT_TICKS ticks so one
 * capture compares them): bit 0 = single-buffered FIFO (else double),
 * bit 1 = POWER.ISOUpdate on (else off). Variant 0 is the normal tap set-up
 * (double-buffered, ISOUpdate off; run 9 showed ISOUpdate on loses packets).
 * The left counter is untouched, so frame continuity is still checked, and
 * the diag frames mark where each packet starts.
 */
#include "usb_audio.c"

#ifndef UA_TAP_TX_L
#define UA_TAP_TX_L ((const volatile int *)0x11f038b0u)
#define UA_TAP_TX_R ((const volatile int *)0x11f038f0u)
#endif
/* Dry input: RX unpack 11818b20 (called at 11818bb0, earlier in the same Swi)
   stores SMPY32(codec word, 0x80000000), i.e. the negated full-scale int32
   sample, for the left ADC (MIC3L, the guitar jack) at 11f03730 and the right
   ADC at 11f03770 (recon/16; 11818b58 MVKH 0x80000000, 11818b84 SUBAW B6,0x10
   -> 11f03730). The effect chain works on that same value, so its high half
   keeps the dry input in the wet path's polarity. */
#ifndef UA_TAP_RX_L
#define UA_TAP_RX_L ((const volatile int *)0x11f03730u)
#define UA_TAP_RX_R ((const volatile int *)0x11f03770u)
/* Mix buses read by the patch-level stage 11817a90 (called at 11818c44,
   before the pack at 11818c64), docs/helpers/RHYTHM_LOOPER_TAP_2026-10-17.md
   R5: 11f03830/11f03870 stereo (added to the chain output), 11f03930 mono
   (x gain c011acd0), 11f03970 mono (address published, no consumer found).
   Float, 16 per channel, 1.0 = full scale (11818428 scales by 2^31). Their
   producer is unknown: the 8-channel build sends them so a take shows what
   they carry (rhythm, looper, ...). Read-only. */
#define UA_TAP_BUS_L ((const volatile float *)0x11f03830u)
#define UA_TAP_BUS_R ((const volatile float *)0x11f03870u)
#define UA_TAP_BUS_M ((const volatile float *)0x11f03930u)
#define UA_TAP_BUS_X ((const volatile float *)0x11f03970u)
#endif
#if defined(UA_BENCH) && !defined(UA_FX)
#error "the bench build extends the FX layout"
#endif
#if defined(UA_FX) && !defined(UA_STEMS)
#error "the guitar-FX pair is part of the stems layout"
#endif
#if UA_NCH == 10 && !(defined(UA_FX) && !defined(UA_BENCH))
#error "the 10-channel layout is the FX layout without the bench frames"
#endif
#if defined(UA_STEMS) && UA_NCH != 8 && UA_NCH != 10
#error "the drums/looper stems need the 8-channel layout"
#endif
#ifdef UA_STEMS
/* Drums and looper alone (docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md,
   checked against main.dis). Both are added in place into the float chain
   bus 11f037b0 (L) / 11f037f0 (R), 16 samples each, 1.0 = full scale:
   - drums: 11817640, called at 11818d64 inside 11818d60 (Swi step 15). When
     the rhythm flag 11f03d54 is set it computes buf = (buf + drum) * m with m
     the float at 11f03d1c (A18 = 11f03d54 - 0x48 + 0x38 - 0x24 - 4, loaded at
     118178a4/118178bc); when clear it leaves the bus alone (118176a4..d8).
   - looper: 118164c0, reached through the dispatcher 11818e60 called at
     11818bc0 (A4 = 0, Pre) and 11818c50 (A4 = 1, Post); the table 11f03ed0
     holds it in one slot and a no-op in the other. It adds its mono playback
     to both channels with a level/fade factor (11816db8..11816e1c). */
#ifndef UA_MIX_L
#define UA_MIX_L ((volatile float *)0x11f037b0u)
#define UA_MIX_R ((volatile float *)0x11f037f0u)
#define UA_RHYTHM_ON (*(const volatile int *)0x11f03d54u)
#define UA_DRUM_GAIN (*(const volatile float *)0x11f03d1cu)
#define UA_STOCK_DRUMS() (((void (*)(void))0x11817640u)())
#define UA_STOCK_LOOPER(pos) (((void (*)(int))0x11818e60u)(pos))
#endif
#endif
#if UA_NCH == 8 && defined(UA_TAP_PATTERN)
#error "the pattern diagnostic build is 2-channel only"
#endif
#define UA_WPF (UA_NCH / 2u)   /* ring words per frame: two 16-bit channels per word */
#ifndef UA_TAP_STOCK_PACK
#define UA_TAP_STOCK_PACK() (((void (*)(void))0x11818aa0u)())
#endif

#ifdef __TI_COMPILER_VERSION__
#define UA_SMPY32(a, b) _smpy32((a), (b))
#define UA_SSHL(a, n)   _sshl((a), (n))
#else
static int UA_SMPY32(int a, int b)
{
    long long p = (long long)a * (long long)b;
    if (a == (int)0x80000000 && b == (int)0x80000000)
        return 0x7fffffff;
    return (int)(p >> 31);
}
static int UA_SSHL(int a, unsigned n)
{
    long long v = (long long)a << n;
    if (v > 0x7fffffffLL)
        return 0x7fffffff;
    if (v < -0x80000000LL)
        return (int)0x80000000;
    return (int)v;
}
#endif

#define UA_TAP_BLOCK   16u     /* frames per audio Swi block (recon/16) */
#define UA_TAP_FRAMES  256u    /* ring size, power of two: 5.8 ms */
#define UA_TAP_MASK    (UA_TAP_FRAMES - 1u)
#define UA_TAP_TARGET  80u     /* fill above this at SOF -> send 45 */
#define UA_TAP_PRIME   128u    /* fill needed before (re)starting */
#define UA_TAP_GAIN    0x4534fd79   /* stock pack constant, Q31 */

typedef struct {
    volatile u32 ring_wr;      /* frames produced, written by the Swi only */
    volatile u32 ring_rd;      /* frames consumed, written by the Hwi only */
    volatile u32 primed;       /* Hwi only */
    volatile u32 blocks;       /* Swi: blocks stored */
    volatile u32 overruns;     /* Swi: blocks dropped, ring full */
    volatile u32 underruns;    /* Hwi: packets short of frames */
    volatile u32 packets45;    /* Hwi: 45-frame packets sent from the ring */
} usb_audio_tap_t;

#pragma DATA_SECTION(usb_audio_tap, ".ua_state")
usb_audio_tap_t usb_audio_tap = { 0, 0, 0, 0, 0, 0, 0 };

/* One stereo frame per word: left in the low half, right in the high half,
   which is the UAC1 16-bit stereo byte order on a little-endian FIFO. */
#pragma DATA_SECTION(usb_audio_ring, ".ua_state")
volatile u32 usb_audio_ring[UA_TAP_FRAMES * UA_WPF];

#ifdef UA_TAP_PATTERN
#pragma DATA_SECTION(ua_pattern_frame, ".ua_state")
volatile u32 ua_pattern_frame;     /* Swi only: frames generated */
#pragma DATA_SECTION(ua_pattern_phase, ".ua_state")
volatile u32 ua_pattern_phase;     /* Swi only: ua_pattern_frame % 44, kept without a divide */

static const short ua_pattern_sine[44] = {    /* 16384 sin(2 pi (i + 0.5) / 44) */
    1169, 3483, 5726, 7852, 9819, 11585, 13116, 14380, 15351, 16010, 16342,
    16342, 16010, 15351, 14380, 13116, 11585, 9819, 7852, 5726, 3483, 1169,
    -1169, -3483, -5726, -7852, -9819, -11585, -13116, -14380, -15351, -16010, -16342,
    -16342, -16010, -15351, -14380, -13116, -11585, -9819, -7852, -5726, -3483, -1169
};

static inline void ua_pattern_advance(u32 n)
{
    u32 p = ua_pattern_phase + n;

    while (p >= 44u)
        p -= 44u;
    ua_pattern_phase = p;
    ua_pattern_frame += n;
}
#endif

#ifdef UA_TAP_PATTERN
#define USB_FRAME        USB_AUDIO_REG16(0x01e0040cu)
#define TXCSR_UNDERRUN   0x0004u

#define UA_VARIANT_TICKS 4000u   /* 4 s per FIFO set-up variant */

typedef struct {
    volatile u32 packets;      /* ring packets loaded */
    volatile u32 same_frame;   /* ticks that saw an unchanged FRAME */
    volatile u32 ticks;        /* streaming ticks in the current variant */
    volatile u32 variant;      /* FIFO set-up in force, 0..3 */
    volatile u32 underrun;     /* SOFs that found TXCSR UnderRun set */
    volatile u32 frame_skips;  /* USB frames that passed without a tick */
    volatile u32 last_frame;   /* FRAME at the previous tick, 0x8000 = none yet */
    volatile u32 txcsr;        /* TXCSR as read at the latest tick */
} ua_pattern_diag_t;

#pragma DATA_SECTION(ua_pattern_diag, ".ua_state")
ua_pattern_diag_t ua_pattern_diag = { 0, 0, 0, 0, 0, 0, 0x8000u, 0 };

static u32 ua_pattern_diag_word(u32 fill)
{
    u32 tag = ua_pattern_diag.packets & 7u;
    u32 v[8];

    v[0] = ua_pattern_diag.packets >> 3;
    v[1] = usb_audio_state.missed_sof;
    v[2] = ua_pattern_diag.underrun;
    v[3] = (ua_pattern_diag.variant << 11) | (ua_pattern_diag.frame_skips & 0x7ffu);
    v[4] = fill;
    v[5] = ua_pattern_diag.same_frame;
    v[6] = ((usb_audio_tap.overruns & 0x3fu) << 7) | (usb_audio_tap.underruns & 0x7fu);
    v[7] = ua_pattern_diag.txcsr;
    return (tag << 13) | (v[tag] & 0x1fffu);
}

/* Every tick, before anything else: frame-number gap and TXCSR status. */
static void ua_pattern_diag_tick(void)
{
    u32 f = USB_FRAME & 0x7ffu, last = ua_pattern_diag.last_frame;
    u32 csr = USB_EP1_TXCSR;

    if (last != 0x8000u && ((f - last) & 0x7ffu) > 1u)
        ua_pattern_diag.frame_skips += ((f - last) & 0x7ffu) - 1u;
    if (last == f)
        ua_pattern_diag.same_frame++;
    ua_pattern_diag.last_frame = f;
    ua_pattern_diag.txcsr = csr;
    if (csr & TXCSR_UNDERRUN)
        ua_pattern_diag.underrun++;
}

/* Hwi context, inside the stock USB interrupt (so no other USB code runs
   between the INDEX writes). Returns 1 when the set-up changed this tick:
   the FIFO was flushed and nothing is loaded until the next tick. */
static u32 ua_pattern_variant_tick(void)
{
    u32 want, idx;

    if (++ua_pattern_diag.ticks < UA_VARIANT_TICKS)
        return 0;
    ua_pattern_diag.ticks = 0;
    want = (ua_pattern_diag.variant + 1u) & 3u;
    idx = USB_INDEX;
    USB_INDEX = 1;
    USB_TXFIFOSZ = (want & 1u) ? 0x05u : 0x15u;      /* 256 B single : 2 x 256 B */
    USB_INDEX = idx;
    if (want & 2u)
        USB_POWER |= POWER_ISOUPDATE;
    else
        USB_POWER &= ~POWER_ISOUPDATE;
    USB_EP1_TXCSR = TXCSR_MODE | TXCSR_ISO | TXCSR_FLUSHFIFO;
    USB_EP1_TXCSR = TXCSR_MODE | TXCSR_ISO | TXCSR_FLUSHFIFO;
    ua_pattern_diag.variant = want;
    return 1;
}
#endif

static inline u32 ua_tap_sample(int x)
{
    return ((u32)UA_SSHL(UA_SMPY32(x, UA_TAP_GAIN), 2) >> 16) & 0xffffu;
}

/* Dry input word (RX unpack's full-scale int32) -> 16-bit USB sample. */
static inline u32 ua_tap_dry(int x)
{
    return ((u32)x >> 16) & 0xffffu;
}

#if UA_NCH >= 8
#ifdef __TI_COMPILER_VERSION__
#define UA_SPINT(f) _spint(f)          /* SPINT: round, saturate to int32 */
#else
static int UA_SPINT(float f)
{
    double d = (double)f;
    if (d >= 2147483647.0)
        return 0x7fffffff;
    if (d <= -2147483648.0)
        return (int)0x80000000;
    return (int)(d < 0 ? d - 0.5 : d + 0.5);
}
#endif
/* Float bus sample (1.0 = full scale) -> 16-bit: saturate at int32, high half,
   the same truncation as the pack path. */
static inline u32 ua_tap_float(float x)
{
    return ((u32)UA_SPINT(x * 2147483648.0f) >> 16) & 0xffffu;
}
#endif

#ifdef UA_STEMS
/* Swi only (the audio Swi is not reentrant), so plain statics. */
static float ua_stem_drum_l[UA_TAP_BLOCK], ua_stem_drum_r[UA_TAP_BLOCK];
static float ua_stem_loop[UA_TAP_BLOCK];
static float ua_stem_save_l[UA_TAP_BLOCK], ua_stem_save_r[UA_TAP_BLOCK];
#ifdef UA_BENCH
/* CPU bench (docs/CF_BENCH_2026-10-17.md): TSCL time stamps at fixed points of
   the audio Swi, sent as one 16-word frame per block on USB channel 8 (instead
   of the looper). Points: Pre looper call (11818bc0), the start of each slot
   (the 11818eb0 veneer, called by the slot loop before slot k's callback;
   slot index at c0184f98, B14 = c0184e00 + 102 x 4), Post looper call
   (11818c50) and the TX pack (11818c64). The slot loop is skipped while
   c0184f94 != 0 (tuner mute): the frame's slot mask then says which slots ran. */
#ifndef UA_TSCL
extern __cregister volatile unsigned int TSCL;   /* CPU cycle counter (c6x.h), started by stock */
#define UA_TSCL() TSCL
#define UA_SLOT_INDEX (*(const volatile int *)0xc0184f98u)
#define UA_SLOT_CTX ((void *)0x11f03b48u)
#endif
#define UA_BENCH_SYNC 0x7e5au
enum { UA_B_PRE, UA_B_S0, UA_B_POST = UA_B_S0 + 5, UA_B_TX, UA_B_N };
static u32 ua_bench_t[UA_B_N];
static u32 ua_bench_mask, ua_bench_seq, ua_bench_prev_pre;
static u32 ua_bench_frame[UA_TAP_BLOCK];
#ifdef UA_PROBE
static u32 ua_watch_frame[16];        /* built by ua_watch_build, packed on channel 7 */
#endif

/* Replaces the 11818eb0 veneer's target c01502cc, which only returns the
   shared context table 0x11f03b48 (c01502cc: MVK/MVKH A4; BNOP B3,5). */
void *ua_slot_enter(void)
{
    u32 t = UA_TSCL();
    u32 k = (u32)UA_SLOT_INDEX;
    if (k < 5u) {
        ua_bench_t[UA_B_S0 + k] = t;
        ua_bench_mask |= 1u << k;
    }
    return UA_SLOT_CTX;
}
#endif
#ifdef UA_FX
/* Guitar FX: the bus as the Post looper call (11818c50) finds it, i.e. after
   the slot loop, the patch-level stage 11817a90 (11818c44) and 11818ea0
   (11818c48), before the Post looper, the drums and the master level
   (11818d60). A Pre looper (11818bc0) plays through the effects, so it is
   in here too. */
static float ua_stem_fx_l[UA_TAP_BLOCK], ua_stem_fx_r[UA_TAP_BLOCK];
#endif

/* Replaces the CALLP 11818e60 at 11818bc0 and 11818c50 (via a veneer).
   Looper alone = bus after - bus before (left; the looper adds the same mono
   signal to both). Exact while its level factor is 1; during a fade the
   stem also carries (factor - 1) x the bus. Only one of the two calls runs
   the looper, the other adds nothing, so the stem accumulates; the TX tap
   clears it after each block. The pedal's own audio is not changed. */
void ua_looper_tap(int pos)
{
    u32 i;
#ifdef UA_BENCH
    ua_bench_t[pos ? UA_B_POST : UA_B_PRE] = UA_TSCL();
#endif

    for (i = 0; i < UA_TAP_BLOCK; i++)
        ua_stem_save_l[i] = UA_MIX_L[i];
#ifdef UA_FX
    if (pos == 1)
        for (i = 0; i < UA_TAP_BLOCK; i++) {
            ua_stem_fx_l[i] = ua_stem_save_l[i];
            ua_stem_fx_r[i] = UA_MIX_R[i];
        }
#endif
    UA_STOCK_LOOPER(pos);
    for (i = 0; i < UA_TAP_BLOCK; i++)
        ua_stem_loop[i] += UA_MIX_L[i] - ua_stem_save_l[i];
}

/* Replaces the CALLP 11817640 at 11818d64 (via a veneer). With the rhythm on,
   the drum mixer runs on a zeroed bus, so it leaves drum x m there: that is
   the stem. The bus then becomes saved x m + stem, which is the stock
   (saved + drum) x m: bit-identical for m = 1, within one rounding step
   otherwise. With the rhythm off the stock call runs untouched. */
void ua_drums_tap(void)
{
    u32 i;
    float m;

    if (!UA_RHYTHM_ON) {
        UA_STOCK_DRUMS();
        for (i = 0; i < UA_TAP_BLOCK; i++)
            ua_stem_drum_l[i] = ua_stem_drum_r[i] = 0.0f;
        return;
    }
    for (i = 0; i < UA_TAP_BLOCK; i++) {
        ua_stem_save_l[i] = UA_MIX_L[i];
        ua_stem_save_r[i] = UA_MIX_R[i];
        UA_MIX_L[i] = 0.0f;
        UA_MIX_R[i] = 0.0f;
    }
    UA_STOCK_DRUMS();
    m = UA_DRUM_GAIN;
    for (i = 0; i < UA_TAP_BLOCK; i++) {
        float dl = UA_MIX_L[i], dr = UA_MIX_R[i];
        ua_stem_drum_l[i] = dl;
        ua_stem_drum_r[i] = dr;
        UA_MIX_L[i] = ua_stem_save_l[i] * m + dl;
        UA_MIX_R[i] = ua_stem_save_r[i] * m + dr;
    }
}
#endif

/* Swi context. Bounded: 16 frames, no waits. l / r = processed output (TX
   left / right): USB channels 1-2, the pedal's stereo output. With 8 channels
   (owner, 2026-10-17: keep stereo, add the DI and internal sources):
     3 dry input (left ADC, guitar jack)   4 right ADC (wiring unknown)
     5-6 stereo mix bus 11f03830/70        7 mono mix bus 11f03930
     8 bus 11f03970
   Every source is only read, after the stock code finished it this block. */
void usb_audio_tap_block(const volatile int *l, const volatile int *r)
{
    u32 w, i;

    if (!usb_audio_state.stream_enabled)
        return;
    w = usb_audio_tap.ring_wr;
    if (w - usb_audio_tap.ring_rd > UA_TAP_FRAMES - UA_TAP_BLOCK) {
        usb_audio_tap.overruns++;
#ifdef UA_TAP_PATTERN
        ua_pattern_advance(UA_TAP_BLOCK);
#endif
        return;
    }
#ifdef UA_TAP_PATTERN
    (void)l; (void)r;
    for (i = 0; i < UA_TAP_BLOCK; i++) {
        usb_audio_ring[(w + i) & UA_TAP_MASK] = (ua_pattern_frame & 0xffffu) |
            ((u32)(unsigned short)ua_pattern_sine[ua_pattern_phase] << 16);
        ua_pattern_advance(1u);
    }
#else
#if UA_NCH == 2
    for (i = 0; i < UA_TAP_BLOCK; i++)
        usb_audio_ring[(w + i) & UA_TAP_MASK] =
            ua_tap_sample(l[i]) | (ua_tap_sample(r[i]) << 16);
#else
    for (i = 0; i < UA_TAP_BLOCK; i++) {
        volatile u32 *f = &usb_audio_ring[((w + i) & UA_TAP_MASK) * UA_WPF];
#ifdef UA_FX
        /* 1-2: the output stage's words (11f038b0/f0) without the pack's
           x 2.16 converter gain (SMPY32 0x4534fd79, SSHL 2), which clipped
           on USB (take8_identify: 1374 samples). Same level as 3-4 had. */
        f[0] = ua_tap_dry(l[i]) | (ua_tap_dry(r[i]) << 16);
        f[1] = ua_tap_float(ua_stem_fx_l[i]) | (ua_tap_float(ua_stem_fx_r[i]) << 16);
#else
        f[0] = ua_tap_sample(l[i]) | (ua_tap_sample(r[i]) << 16);
        f[1] = ua_tap_dry(UA_TAP_RX_L[i]) | (ua_tap_dry(UA_TAP_RX_R[i]) << 16);
#endif
#if UA_NCH == 10
        /* every pair usable as a stereo track (owner, 2026-10-18): 7-8 DI on both,
           9-10 looper on both */
        f[2] = ua_tap_float(ua_stem_drum_l[i]) | (ua_tap_float(ua_stem_drum_r[i]) << 16);
        f[3] = ua_tap_float(UA_TAP_BUS_M[i]) * 0x10001u;
        f[4] = ua_tap_float(ua_stem_loop[i]) * 0x10001u;
#elif defined(UA_PAIRS8)
        /* 8 channels, every pair usable (fallback if 10 do not open): 7-8 DI on both, no looper */
        f[2] = ua_tap_float(ua_stem_drum_l[i]) | (ua_tap_float(ua_stem_drum_r[i]) << 16);
        f[3] = ua_tap_float(UA_TAP_BUS_M[i]) * 0x10001u;
#elif defined(UA_PROBE)
        /* CF Probe: 7 = watch stream, 8 = bench timing frames */
        f[2] = ua_tap_float(ua_stem_drum_l[i]) | (ua_tap_float(ua_stem_drum_r[i]) << 16);
        f[3] = ua_watch_frame[i] | (ua_bench_frame[i] << 16);
#elif defined(UA_BENCH)
        f[2] = ua_tap_float(ua_stem_drum_l[i]) | (ua_tap_float(ua_stem_drum_r[i]) << 16);
        f[3] = ua_tap_float(UA_TAP_BUS_M[i]) | (ua_bench_frame[i] << 16);
#elif defined(UA_STEMS)
        f[2] = ua_tap_float(ua_stem_drum_l[i]) | (ua_tap_float(ua_stem_drum_r[i]) << 16);
        f[3] = ua_tap_float(UA_TAP_BUS_M[i]) | (ua_tap_float(ua_stem_loop[i]) << 16);
#else
        f[2] = ua_tap_float(UA_TAP_BUS_L[i]) | (ua_tap_float(UA_TAP_BUS_R[i]) << 16);
        f[3] = ua_tap_float(UA_TAP_BUS_M[i]) | (ua_tap_float(UA_TAP_BUS_X[i]) << 16);
#endif
    }
#endif
#endif
    usb_audio_tap.ring_wr = w + UA_TAP_BLOCK;     /* publish last */
    usb_audio_tap.blocks++;
}

/* Replaces the stock CALLP 11818aa0 at 11818c64 (via the 11818c88 veneer).
   The Swi keeps nothing in scratch registers across that call. */
#ifdef UA_BENCH
/* Frame: sync, seq (11 bits) | slot mask << 11, then seven u32 as lo, hi:
   slot 0..3 = start(k+1) - start(k); slot 4 = Post looper - start(4) (also
   holds patch level 11817a90 and the output EQ slot, measured with an empty
   patch); busy = TX - Pre looper; period = Pre looper - previous Pre looper. */
#ifdef UA_WATCHDOG
/* Slot watchdog (docs/FW_RND_ANSWERS_2026-10-22.md, S10 design). A slot whose
   measured time exceeds UA_WD_LIMIT cycles for UA_WD_TRIPS blocks in a row is
   bypassed: its entry in the live callback table 0x118133e0 (the function the
   slot loop at 11818c0c loads and calls) is replaced by ua_wd_noop, which
   leaves the bus untouched (dry). The loader owns the table: when it installs
   a new function in that slot (the user picks another effect or reloads the
   patch), the slot is watched again from zero. Only slow effects are caught;
   a faulting effect still ends in the SYS/BIOS exception halt. The tripped
   mask goes out in bits 11..15 of the period's high word (period < 2^27). */
#ifndef UA_SLOT_TABLE
#define UA_SLOT_TABLE ((void *volatile *)0x118133e0u)
#endif
#ifndef UA_WD_LIMIT
#define UA_WD_LIMIT 64000u      /* cycles per 16-frame block, about 40% of the period */
#endif
#ifndef UA_WD_TRIPS
#define UA_WD_TRIPS 16u         /* blocks in a row, about 6 ms */
#endif
static void *ua_wd_seen[5];
static u32 ua_wd_over[5];
static u32 ua_wd_tripped;

void ua_wd_noop(void)
{
}

static void ua_wd_check(const u32 *v, u32 ran)
{
    u32 k;
    for (k = 0; k < 5u; k++) {
        void *fn = UA_SLOT_TABLE[k];
        if (fn == (void *)ua_wd_noop)
            continue;                           /* bypassed until the loader replaces it */
        if (fn != ua_wd_seen[k] || (ua_wd_tripped >> k & 1u)) {
            ua_wd_seen[k] = fn;                 /* a new or reinstalled effect */
            ua_wd_over[k] = 0;
            ua_wd_tripped &= ~(1u << k);
            continue;
        }
        if (!(ran >> k & 1u))
            continue;
        if (v[k] <= UA_WD_LIMIT) {
            ua_wd_over[k] = 0;
        } else if (++ua_wd_over[k] >= UA_WD_TRIPS) {
            UA_SLOT_TABLE[k] = (void *)ua_wd_noop;
            ua_wd_tripped |= 1u << k;
            ua_wd_over[k] = 0;
        }
    }
}
#endif

#ifdef UA_PROBE
/* CF Probe watch stream (docs/FW_RND_BRIEF5_2026-10-22.md): USB channel 7 carries,
   every block, one 16-word frame with six 32-bit words read from a list of up
   to UA_WATCH_MAX addresses, walking the list round-robin:
     [0] sync 0x7e5b, [1] sequence (8 bits) | list length << 8,
     [2] index of the first of the six entries, [3..14] six u32 as lo, hi,
     [15] XOR of words [0..14].
   Reads are word reads of addresses the list accepted (ua_watch_ok: on-chip L2
   and L1D RAM and the first 8 MB of SDRAM, word aligned), so a bad list can
   never touch a peripheral register. The default list is CF Probe watch list v1
   (looper and drum state, docs/helpers/FW_RND_F9_LOOPER_DRUMS_FLASH_2026-10-22.md). */
#define UA_WATCH_SYNC 0x7e5bu
#define UA_WATCH_MAX 64u
#define UA_WATCH_PER 6u
static u32 ua_watch_addr[UA_WATCH_MAX] = {
    0x11f03c58u, 0x11f03c54u, 0x11f03e38u, 0x11f03c64u, 0x11f03cd8u, 0x11f03ed0u,
    0x11f03ed4u, 0xc011aca8u, 0xc011acacu, 0xc011acb0u, 0xc011acb4u, 0xc011acc0u,
    0xc0184fb0u, 0xc0184fb4u, 0xc0184fb8u, 0x11f03d54u, 0x11f03d1cu, 0x11f03d08u,
    0x11f03d0cu, 0x11f03d14u, 0x11f03d58u, 0x11f03d5cu, 0x11f03d60u, 0x11812f78u,
    0x118133b4u, 0x118133bcu, 0xc011ada4u, 0xc011ada8u, 0x1181191cu, 0x11f03e34u,
    0x11812f74u, 0x1180312cu
};
static u32 ua_watch_n = 32u, ua_watch_pos, ua_watch_seq;
#ifndef UA_WATCH_READ
#define UA_WATCH_READ(a) (*(const volatile u32 *)(a))
#endif

u32 ua_watch_ok(u32 a)
{
    if (a & 3u)
        return 0;
    return (a >= 0x11800000u && a < 0x11840000u)      /* L2 RAM */
        || (a >= 0x11f00000u && a < 0x11f08000u)      /* L1D RAM */
        || (a >= 0xc0000000u && a < 0xc0800000u);     /* SDRAM, first 8 MB */
}

/* Replace the list (from the SysEx handler, MIDI task): entries that fail
   ua_watch_ok are dropped. Returns the new length. Runs with the Swi able to
   preempt: the length is published last, after the addresses. */
u32 ua_watch_set(const u32 *addr, u32 n)
{
    u32 i, k = 0;
    ua_watch_n = 0;
    for (i = 0; i < n && k < UA_WATCH_MAX; i++)
        if (ua_watch_ok(addr[i]))
            ua_watch_addr[k++] = addr[i];
    ua_watch_pos = 0;
    ua_watch_n = k;
    return k;
}

static void ua_watch_build(void)
{
    u32 k, x = 0, n = ua_watch_n, pos = ua_watch_pos;
    if (pos >= n)
        pos = 0;
    ua_watch_frame[0] = UA_WATCH_SYNC;
    ua_watch_frame[1] = (ua_watch_seq++ & 0xffu) | (n & 0xffu) << 8;
    ua_watch_frame[2] = pos;
    for (k = 0; k < UA_WATCH_PER; k++) {
        u32 v = 0;
        if (n) {
            u32 j = pos + k;                    /* no RTS here: wrap without % */
            while (j >= n)
                j -= n;
            u32 a = ua_watch_addr[j];
            if (ua_watch_ok(a))
                v = UA_WATCH_READ(a);
        }
        ua_watch_frame[3 + 2 * k] = v & 0xffffu;
        ua_watch_frame[4 + 2 * k] = v >> 16;
    }
    pos += UA_WATCH_PER;
    while (n && pos >= n)
        pos -= n;
    ua_watch_pos = n ? pos : 0;
    for (k = 0; k < 15u; k++)
        x ^= ua_watch_frame[k];
    ua_watch_frame[15] = x & 0xffffu;
}
#endif

static void ua_bench_build(void)
{
    u32 v[7], k, *t = ua_bench_t;

    for (k = 0; k < 4u; k++)
        v[k] = t[UA_B_S0 + k + 1] - t[UA_B_S0 + k];
    v[4] = t[UA_B_POST] - t[UA_B_S0 + 4];
    v[5] = t[UA_B_TX] - t[UA_B_PRE];
    v[6] = t[UA_B_PRE] - ua_bench_prev_pre;
    ua_bench_prev_pre = t[UA_B_PRE];
#ifdef UA_WATCHDOG
    ua_wd_check(v, ua_bench_mask);
    v[6] = (v[6] & 0x07ffffffu) | (ua_wd_tripped & 0x1fu) << 27;
#endif
    ua_bench_frame[0] = UA_BENCH_SYNC;
    ua_bench_frame[1] = (ua_bench_seq++ & 0x7ffu) | (ua_bench_mask & 0x1fu) << 11;
    for (k = 0; k < 7u; k++) {
        ua_bench_frame[2 + 2 * k] = v[k] & 0xffffu;
        ua_bench_frame[3 + 2 * k] = v[k] >> 16;
    }
    ua_bench_mask = 0;
#ifdef UA_PROBE
    ua_watch_build();
#endif
}
#endif

void ua_tx_pack_tap(void)
{
#ifdef UA_BENCH
    ua_bench_t[UA_B_TX] = UA_TSCL();
    ua_bench_build();
#endif
    UA_TAP_STOCK_PACK();
    usb_audio_tap_block(UA_TAP_TX_L, UA_TAP_TX_R);
#ifdef UA_STEMS
    {
        u32 i;
        for (i = 0; i < UA_TAP_BLOCK; i++)
            ua_stem_loop[i] = 0.0f;
    }
#endif
}

/* Hwi context: bounded (at most 45 FIFO writes), never spins, direct EP1
   registers only. */
void usb_audio_sof_tick_tap(void)
{
    u32 n, i, w, r, fill, have;

#ifdef UA_TAP_PATTERN
    if (usb_audio_state.stream_enabled) {
        ua_pattern_diag_tick();
        if (ua_pattern_variant_tick())
            return;
    }
#endif
    if (!usb_audio_state.stream_enabled) {
        /* Consumer-side discard: a restart never replays an old stream.
           The Swi stores nothing while the stream is off. */
        usb_audio_tap.ring_rd = usb_audio_tap.ring_wr;
        usb_audio_tap.primed = 0;
        usb_audio_state.missed_sof++;
        return;
    }
    if (USB_EP1_TXCSR & TXCSR_TXPKTRDY) {
        /* Host not polling (late after alt 1, or stalled). Keep only the
           newest UA_TAP_PRIME frames so the Swi never overruns: an overrun
           drops the newest block, and priming on the stored frames would
           then join two distant stretches (run 10: a splice 128 frames into
           the stream). A stall long enough to fill the ring re-primes. */
        w = usb_audio_tap.ring_wr;
        if (!usb_audio_tap.primed ||
            w - usb_audio_tap.ring_rd > UA_TAP_FRAMES - 2u * UA_TAP_BLOCK) {
            usb_audio_tap.primed = 0;
            if (w - usb_audio_tap.ring_rd > UA_TAP_PRIME)
                usb_audio_tap.ring_rd = w - UA_TAP_PRIME;
        }
        usb_audio_state.missed_sof++;
        return;
    }

    w = usb_audio_tap.ring_wr;
    r = usb_audio_tap.ring_rd;
    fill = w - r;

    if (!usb_audio_tap.primed) {
        if (fill >= UA_TAP_PRIME) {
            /* Start from the newest UA_TAP_PRIME frames: stale frames from
               an earlier stream are dropped here, by the consumer. */
            r = w - UA_TAP_PRIME;
            fill = UA_TAP_PRIME;
            usb_audio_tap.primed = 1;
        } else {
            /* Not primed yet: keep the host fed with the silence pattern. */
            n = (usb_audio_state.frame_phase < 1) ? 45u : 44u;
            usb_audio_state.frame_phase++;
            if (usb_audio_state.frame_phase >= 10)
                usb_audio_state.frame_phase = 0;
            for (i = 0; i < n * UA_WPF; i++)
                USB_EP1_FIFO = 0;
            USB_EP1_TXCSR = TXCSR_MODE | TXCSR_ISO | TXCSR_TXPKTRDY;
            usb_audio_state.serviced_sof++;
            return;
        }
    }

    n = (fill > UA_TAP_TARGET) ? 45u : 44u;
    have = (fill < n) ? fill : n;
#ifdef UA_TAP_PATTERN
    if (have) {
        USB_EP1_FIFO = (usb_audio_ring[r & UA_TAP_MASK] & 0xffffu) |
                       (ua_pattern_diag_word(fill) << 16);
        ua_pattern_diag.packets++;
    }
    for (i = have ? 1u : 0u; i < have; i++)
        USB_EP1_FIFO = usb_audio_ring[(r + i) & UA_TAP_MASK];
    for (; i < n; i++)
        USB_EP1_FIFO = 0;
#elif UA_NCH == 2
    for (i = 0; i < have; i++)
        USB_EP1_FIFO = usb_audio_ring[(r + i) & UA_TAP_MASK];
    for (; i < n; i++)
        USB_EP1_FIFO = 0;
#else
    for (i = 0; i < have; i++) {
        const volatile u32 *f = &usb_audio_ring[((r + i) & UA_TAP_MASK) * UA_WPF];
        USB_EP1_FIFO = f[0];
        USB_EP1_FIFO = f[1];
        USB_EP1_FIFO = f[2];
        USB_EP1_FIFO = f[3];
#if UA_NCH == 10
        USB_EP1_FIFO = f[4];
#endif
    }
    for (i = have * UA_WPF; i < n * UA_WPF; i++)
        USB_EP1_FIFO = 0;
#endif
    usb_audio_tap.ring_rd = r + have;
    if (have < n) {
        usb_audio_tap.underruns++;
        usb_audio_tap.primed = 0;
    } else if (n == 45u) {
        usb_audio_tap.packets45++;
    }

    USB_EP1_TXCSR = TXCSR_MODE | TXCSR_ISO | TXCSR_TXPKTRDY;   /* 0x6001 */
    usb_audio_state.serviced_sof++;
}

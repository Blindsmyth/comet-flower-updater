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
volatile u32 usb_audio_ring[UA_TAP_FRAMES];

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

/* Swi context. Bounded: 16 frames, no waits. */
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
    for (i = 0; i < UA_TAP_BLOCK; i++)
        usb_audio_ring[(w + i) & UA_TAP_MASK] =
            ua_tap_sample(l[i]) | (ua_tap_sample(r[i]) << 16);
#endif
    usb_audio_tap.ring_wr = w + UA_TAP_BLOCK;     /* publish last */
    usb_audio_tap.blocks++;
}

/* Replaces the stock CALLP 11818aa0 at 11818c64 (via the 11818c88 veneer).
   The Swi keeps nothing in scratch registers across that call. */
void ua_tx_pack_tap(void)
{
    UA_TAP_STOCK_PACK();
    usb_audio_tap_block(UA_TAP_TX_L, UA_TAP_TX_R);
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
            for (i = 0; i < n; i++)
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
#else
    for (i = 0; i < have; i++)
#endif
        USB_EP1_FIFO = usb_audio_ring[(r + i) & UA_TAP_MASK];
    for (; i < n; i++)
        USB_EP1_FIFO = 0;
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

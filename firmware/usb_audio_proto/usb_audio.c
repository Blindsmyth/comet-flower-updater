/* USB audio "silence stream" prototype for the G1X Four USB0 controller
 * (TI C674x, MUSB-type full-speed controller). Companion to recon/18 item 3
 * and recon/20_usb_audio_proto.md (round 4, Helper B).
 *
 * SCRATCH / PROTOTYPE ONLY: not referenced by firmware/, not wired into any
 * stock call site, no image is built from it. It exists to prove the
 * routines below compile and disassemble sanely for placement at c01a8000
 * (recon/20 item 3). Every stock call site it is designed to replace, and
 * every MMIO address's evidence/confidence, is documented in recon/20.
 *
 * Memory map (CTL2, c01a8000..c01affff, 32 KiB, see usb_audio.cmd):
 *   .ua_state  - state struct (writable)
 *   .const     - descriptor fragments, pointer array source data
 *   .text      - routines below
 *
 * Calling-context requirements (recon/20 item 2):
 *   usb_audio_build_descriptors / usb_audio_descriptor_veneer
 *       Task/init context. Stock equivalent c0160ec0 is CALLP'd from
 *       c0135014 inside the GET_DESCRIPTOR(CONFIGURATION) path, itself
 *       reached from the common control-request dispatcher (task context,
 *       not Hwi/Swi). The veneer (usb_audio.asm) adapts this file's EABI
 *       C function to c0160ec0's own calling convention (out-pointer in
 *       A6, recon/20 2.1) so it could, in principle, be CALLP'd from the
 *       same site unchanged except for the retarget itself.
 *   usb_audio_setup_ep1
 *       Task/init context, run once while the bus is quiescent, AFTER
 *       stock's normal c01212e0-based RX3/TX4 setup so this endpoint's
 *       fixed tail FIFO reservation (0x140..0x33f) is not later
 *       overwritten by c012146e..14c6's generic repacker (recon/18 3.3,
 *       recon/20 2.3).
 *   usb_audio_sof_tick
 *       Hwi context, CPU interrupt 7 / event 19 (recon/18 3.4, recon/20
 *       1.4). Must stay short and bounded: no semaphore, no allocator, no
 *       stock send/message API (recon/17 B4 finding 3). Not wired to any
 *       vector by this file; recon/20 2.4 proposes retargeting c016f770's
 *       MVK/MVKH pair (two absolute-value words) rather than re-encoding
 *       c011fcb4's PC-relative CALLP.
 *
 * Nothing here is built into a firmware image, and no stock byte is
 * patched by compiling this file.
 */

typedef unsigned char  u8;
typedef unsigned short u16;
typedef unsigned int   u32;

/* USB channel count: 2 (stereo, the default, every existing build) or 8
   (multichannel tap build, make_usb_audio_fw.py --tap8; channel map in
   usb_audio_tap.c). 16-bit samples; 45 frames worst case per 1 ms packet. */
#ifndef UA_NCH
#define UA_NCH 2
#endif
#if UA_NCH != 2 && UA_NCH != 8 && UA_NCH != 10
#error "UA_NCH must be 2, 8 or 10"
#endif
#define UA_PKT_MAX   (45u * 2u * UA_NCH)        /* 180, 720 or 900 bytes (<= 1023, one FIFO bank) */
#if UA_NCH == 2
#define UA_FIFOSZ    0x15u   /* 2 x 256 B (size code 5 = 256 B, bit 4 double) */
#else
#define UA_FIFOSZ    0x17u   /* 2 x 1024 B at 0x140..0x93f: free per USB_OPT_A3 (stock uses 0x000..0x13f) */
#endif

/* The host regression harness replaces these lvalues with in-memory registers.
   Target builds always use the physical, volatile MMIO accesses below. */
#ifndef USB_AUDIO_REG8
#define USB_AUDIO_REG8(address)  (*(volatile u8 *)(address))
#define USB_AUDIO_REG16(address) (*(volatile u16 *)(address))
#define USB_AUDIO_REG32(address) (*(volatile u32 *)(address))
#endif

/* ------------------------------------------------------------------ *
 * MMIO: USB0 MUSB-type controller registers actually used here.
 * Confidence is per-register; see recon/20 items 1.3/1.7/2.3 for the
 * disassembly evidence behind each one.
 * ------------------------------------------------------------------ */

/* CONFIRMED: c0121336 (A10 = 0x1e0040e) and c0121338 (STB endpoint# here
   selects which endpoint the indexed registers below address). */
#define USB_INDEX        USB_AUDIO_REG8(0x01e0040eu)

/* CONFIRMED: INDEX+2, c0121406/0c (recon/18 B2, re-traced recon/20 1.7). */
#define USB_TXMAXP       USB_AUDIO_REG16(0x01e00410u)

/* CONFIRMED (recon/20 1.7): INDEX+4, c012142e + the CSR store at
   c0121444. Indexed: only for task-context set-up, never from the SOF Hwi. */
#define USB_TXCSR        USB_AUDIO_REG16(0x01e00412u)

/* CONFIRMED (recon/21 3.3): direct (non-indexed) EP1 TXCSR. Stock reads it
   and clears bit 5 at c0122000..c0122014. The SOF Hwi uses this one so it
   never writes INDEX, which the USB Swi may be in the middle of using. */
#define USB_EP1_TXCSR    USB_AUDIO_REG16(0x01e00512u)

/* CONFIRMED: POWER, byte register. Stock read-modify-writes it (SOFTCONN,
   bit 6: set at c0120e1a..20, cleared at c011ff4a..4c). Bit 7 is ISOUPDATE
   (SPRUFM9H 2.7.1.4.1.2): an ISO packet loaded into the FIFO waits for the
   next SOF. It must be OFF for this endpoint: with it on (and the FIFO double-
   buffered, packets loaded at SOF) 8-63 % of packets reached the host empty or
   cut to 1-2 frames; with it off, 0 lost (hardware runs 6-9, 2026-10-16,
   variants build, docs/CF_USB_MODE_2026-10-16.md). */
#define USB_POWER        USB_AUDIO_REG8(0x01e00401u)
#define POWER_ISOUPDATE  0x80u

/* CONFIRMED: INDEX+0x54, c01213f6/0121402 (recon/18 B2). */
#define USB_TXFIFOSZ     USB_AUDIO_REG8(0x01e00462u)

/* CONFIRMED: INDEX+0x56 per recon/18 3.3's own figure (TXFIFOADDR units
   are 8-byte, EXTU ...,16,19 at c01214c0 converts byte offset to this
   unit encoding; not independently re-derived bit-by-bit in this pass). */
#define USB_TXFIFOADDR   USB_AUDIO_REG16(0x01e00464u)

/* LIKELY, not firmware-confirmed: EP0's FIFO data register is confirmed
   fixed at 0x1e00420 (c0122380/86, non-indexed). Standard MUSB layout
   spaces per-endpoint FIFO data registers 4 bytes apart (FIFO0, FIFO1,
   FIFO2, ...), so EP1's would be 0x1e00424 -- recon/18 3.6 point 5's own
   figure -- but no stock instruction in this image ever touches it
   (expected: stock never configures endpoint 1). Treat as "likely by
   pattern", flagged again in recon/20 item 4 as something to confirm on
   hardware (a bus fault or dead read here would be the first sign this
   guess is wrong). */
#define USB_EP1_FIFO     USB_AUDIO_REG32(0x01e00424u)

/* TXCSR bits (recon/21 3.3). Stock's CSR word is 209 << 6 = 0x3440 =
   MODE | DMAEN | DMAMODE | CLRDATATOG, plus ISO from bmAttributes.
   - ISO (bit 14): CONFIRMED position (c012143a SHL A1,0xe then OR at c0121444).
   - MODE (bit 13, 1 = TX): every 16-bit write rewrites it, so every write
     here must keep it set (0x4001 alone would turn EP1 into an RX endpoint).
   - DMAEN (bit 12) / DMAMODE (bit 10): stock sets both; a PIO producer must
     clear them (usb_audio_set_alt).
   - CLRDATATOG (bit 6), FLUSHFIFO (bit 3), TXPKTRDY (bit 0): CONFIRMED in
     SPRUFM9H Table 65 (PERI_TXCSR). FLUSHFIFO only acts while TXPKTRDY is
     set, and a double-buffered FIFO may need it twice. UNDERRUN (bit 2) is
     set by hardware on an empty IN; every write here clears it. */
#define TXCSR_TXPKTRDY   0x0001u
#define TXCSR_FLUSHFIFO  0x0008u
#define TXCSR_CLRDATATOG 0x0040u
#define TXCSR_DMAMODE    0x0400u
#define TXCSR_DMAEN      0x1000u
#define TXCSR_MODE       0x2000u
#define TXCSR_ISO        0x4000u

/* ------------------------------------------------------------------ *
 * Endpoint-1 FIFO/CSR one-time setup (recon/18 3.3/3.6 point 4,
 * recon/20 2.3). Fixed tail placement, preserving RX3=0x040..0bf and
 * TX4=0x0c0..13f: byte offset 0x140 == FIFOADDR unit 0x28 (8-byte units,
 * recon/18 3.3's own figure).
 * ------------------------------------------------------------------ */
void usb_audio_setup_ep1(void)
{
    USB_INDEX = 1;
    USB_TXMAXP = UA_PKT_MAX;     /* = wMaxPacketSize (180 for 2 channels, recon/17 B5) */
    USB_TXFIFOADDR = 0x28;       /* byte 0x140, recon/18 3.3/3.6 point 4 */
    USB_TXFIFOSZ = UA_FIFOSZ;    /* double-buffered, bank >= one max packet */
    /* TX mode, PIO, toggle reset, FIFO flushed: 0x6048 (recon/21 3.3 fix 1) */
    USB_TXCSR = TXCSR_MODE | TXCSR_ISO | TXCSR_CLRDATATOG | TXCSR_FLUSHFIFO;
}

/* ------------------------------------------------------------------ *
 * State (recon/20 2.2/2.4). Volatile: written from Hwi (sof_tick) and
 * read/written from task context (enable/disable on SET_INTERFACE).
 * ------------------------------------------------------------------ */
typedef struct {
    volatile u8  if2_alt;        /* AudioControl, always alt0 */
    volatile u8  if3_alt;        /* AudioStreaming alt: 0 idle, 1 streaming */
    volatile u8  stream_enabled; /* gate for usb_audio_sof_tick */
    volatile u8  frame_phase;    /* 0..9: selects 44 vs 45 samples (recon/17 B4) */
    volatile u32 missed_sof;     /* bounded counter, never spun on */
    volatile u32 serviced_sof;
} usb_audio_state_t;

#pragma DATA_SECTION(usb_audio_state, ".ua_state")
usb_audio_state_t usb_audio_state = { 0, 0, 0, 0, 0, 0 };

/* No response buffer of our own: the stock EP0 reply buffer c0119fb0 is
   shared by all nine GET paths and has about 512 B of room (recon/21 3.5),
   so usb_audio_copy_descriptors() writes into it through `out`. */

/* One static zero buffer: the payload is always silence, so there is
   nothing to double-buffer or track occupancy for (recon/18 3.6 point 5:
   "precompute zeros"). 45 u32s = 45 stereo 16-bit frames = 180 bytes. */
static const u32 silence_frame[45] = { 0 };

/* ------------------------------------------------------------------ *
 * SOF hook body (recon/18 3.4/3.6 point 5, recon/20 2.4). Hwi context:
 * bounded, no waits, no stock send/message/semaphore API. Derives 44/45
 * from a fixed 10-SOF pattern -- explicitly a synthetic-silence-only
 * simplification (recon/17 B4's "clock design" caveat: a real codec
 * source needs production-count-driven pacing, not a fixed pattern).
 * ------------------------------------------------------------------ */
void usb_audio_sof_tick(void)
{
    u32 n, i;

    if (!usb_audio_state.stream_enabled) {
        usb_audio_state.missed_sof++;
        return;
    }

    n = (usb_audio_state.frame_phase < 1) ? 45u : 44u;
    usb_audio_state.frame_phase++;
    if (usb_audio_state.frame_phase >= 10)
        usb_audio_state.frame_phase = 0;

    /* Direct EP1 registers only: no INDEX write in Hwi context (recon/21 3.3
       fix 3). */
    /* If the previous packet has not been taken (TXPKTRDY still set),
       skip this service rather than spin or wait -- recon/18 3.4's
       explicit instruction ("skip/count missed service rather than
       spin"). */
    if (USB_EP1_TXCSR & TXCSR_TXPKTRDY) {
        usb_audio_state.missed_sof++;
        return;
    }

    for (i = 0; i < n; i++)
        USB_EP1_FIFO = silence_frame[i];   /* bounded: n is 44 or 45 */

    USB_EP1_TXCSR = TXCSR_MODE | TXCSR_ISO | TXCSR_TXPKTRDY;   /* 0x6001 */
    usb_audio_state.serviced_sof++;
}

/* ------------------------------------------------------------------ *
 * IF3 alternate-setting switch (recon/21 3.1 design (b), 3.3 fix 2). Task
 * context, called from the IF3 record callback, which the SETUP decoder
 * c01359e4 runs INSTEAD of stock SET_INTERFACE c0135940 (the callback then
 * ACKs via c015af48(128, 0, 0) and returns 0, as the MIDI callback c0151ed0
 * does). Stock c01212e0 therefore never configures EP1 here; the DMA-clear
 * write stays in case design (a) is used, where EP1 arrives at 0x7440.
 * ------------------------------------------------------------------ */
int usb_audio_set_alt(u32 alt)
{
    /* Reject the complete SETUP wValue, before narrowing it or changing state.
       In particular 0x100 must not be accepted as alternate zero. */
    if (alt > 1u)
        return -1;

    /* Stop the producer first so the Hwi does not load a packet mid-flush. */
    usb_audio_state.stream_enabled = 0;

    if (alt == 1) {
        usb_audio_setup_ep1();
        USB_POWER &= ~POWER_ISOUPDATE;
        /* MUSB rule: clear DMAEN before (or with) DMAMODE, never DMAMODE
           first. Two writes: drop DMAEN, then DMAMODE plus toggle reset and
           flush. */
        USB_EP1_TXCSR = TXCSR_MODE | TXCSR_ISO | TXCSR_DMAMODE;
        USB_EP1_TXCSR = TXCSR_MODE | TXCSR_ISO | TXCSR_CLRDATATOG |
                        TXCSR_FLUSHFIFO;                       /* 0x6048 */
        usb_audio_state.frame_phase = 0;
        usb_audio_state.if3_alt = 1;
        usb_audio_state.stream_enabled = 1;
    } else {
        /* alt 0 has no endpoints; drop anything still queued. Twice: the
           FIFO is double-buffered (SPRUFM9H Table 65 note). */
        USB_EP1_TXCSR = TXCSR_MODE | TXCSR_ISO | TXCSR_FLUSHFIFO;
        USB_EP1_TXCSR = TXCSR_MODE | TXCSR_ISO | TXCSR_FLUSHFIFO;
        usb_audio_state.if3_alt = 0;
    }
    return 0;
}

/* ------------------------------------------------------------------ *
 * Descriptor fragments (recon/20 item 2.1/2.5). The 12 "stock_*" and the
 * device descriptor are the CONFIRMED stock bytes from recon/17 B1
 * finding 1/2, duplicated here only for this prototype; a real
 * integration should point these pointer-array slots at the existing
 * stock ROM copies (this pass traced the FS-path copies' literal
 * addresses inside c0160ec0: device at c017f3dc, config header at
 * c017f400, via the MVK/MVKH pairs at c0160f18..28 and c0160f04..10) and
 * only store the 10 new "uac_*" fragments plus the new config header in
 * this region, to save SDRAM. The "uac_*" fragments and new_config_hdr
 * are recon/17 B5's proposed bytes (design bytes, not recovered from
 * stock firmware) -- their internal self-consistency (bLength vs. byte
 * count, wTotalLength=192 then; 195 since uac_format_i, bNumInterfaces=4, AC header fields) was
 * checked in recon/20 item 1.6 via count_desc.sh.
 * ------------------------------------------------------------------ */

static const u8 device_desc[18] = {
    0x12, 0x01, 0x10, 0x01, 0x00, 0x00, 0x00, 0x40,
    0x86, 0x16, 0xa1, 0x04, 0x00, 0x01, 0x01, 0x02, 0x00, 0x01
};

static const u8 new_config_hdr[9] = {
    0x09, 0x02, 0xc3, 0x00, 0x04, 0x01, 0x00, 0x80, 0xfa
};

static const u8 stock_if0_ac[9]       = { 0x09,0x04,0x00,0x00,0x00,0x01,0x01,0x00,0x00 };
static const u8 stock_ac_header[9]    = { 0x09,0x24,0x01,0x00,0x01,0x09,0x00,0x01,0x01 };
static const u8 stock_if1_ms[9]       = { 0x09,0x04,0x01,0x00,0x02,0x01,0x03,0x00,0x00 };
static const u8 stock_ms_header[7]    = { 0x07,0x24,0x01,0x00,0x01,0x25,0x00 };
static const u8 stock_jack_in_emb[6]  = { 0x06,0x24,0x02,0x01,0x0a,0x00 };
static const u8 stock_jack_in_ext[6]  = { 0x06,0x24,0x02,0x02,0x1e,0x00 };
static const u8 stock_jack_out_emb[9] = { 0x09,0x24,0x03,0x01,0x14,0x01,0x1e,0x01,0x00 };
static const u8 stock_jack_out_ext[9] = { 0x09,0x24,0x03,0x02,0x28,0x01,0x0a,0x01,0x00 };
static const u8 stock_out_ep[9]       = { 0x09,0x05,0x03,0x02,0x40,0x00,0x00,0x00,0x00 };
static const u8 stock_cs_ep1[5]       = { 0x05,0x25,0x01,0x01,0x0a };
static const u8 stock_in_ep[9]        = { 0x09,0x05,0x84,0x02,0x40,0x00,0x00,0x00,0x00 };
static const u8 stock_cs_ep2[5]       = { 0x05,0x25,0x01,0x01,0x14 };

/* iInterface of IF2 (first interface of the audio function): Windows names the
   function, and so the capture endpoint "Line (...)", after it. String 3 is the
   stock empty record c017f41c, repointed by make_controller_fw.py
   --usb-audio-name; 0 (no string, name from the product string) unless the
   build defines UA_AUDIO_STRING. */
#ifndef UA_AUDIO_STRING
#define UA_AUDIO_STRING 0
#endif
static const u8 uac_if2_ac[9]      = { 0x09,0x04,0x02,0x00,0x00,0x01,0x01,0x00,UA_AUDIO_STRING };
static const u8 uac_ac_header[9]   = { 0x09,0x24,0x01,0x00,0x01,0x1e,0x00,0x01,0x03 };
/* Input terminal: bNrChannels = UA_NCH and a wChannelConfig with exactly UA_NCH
   positions: L|R (0x0003) for 2 channels, all eight UAC1 positions (0x00ff, the
   7.1 layout) for 8. With 8 channels but only L|R (8ch build e9b56839, hardware
   2026-10-17) Windows stored a 2-channel endpoint format and refused 8-channel
   streams in WASAPI, MME and WDM-KS ("invalid number of channels"). */
#if UA_NCH == 2
#define UA_CHCFG 0x0003u
#elif UA_NCH == 8
#define UA_CHCFG 0x00ffu
#else
/* 10 positions. UAC1 bits: L R C LFE Ls Rs Lc Rc (0x00ff, as the working 8-channel
   build) + Sl Sr (bits 9, 10) = 0x06ff, a symmetric layout. 0x03ff (with S, bit 8,
   and Sl but no Sr) enumerated but Windows opened no stream on any API (2026-10-18). */
#define UA_CHCFG 0x06ffu
#endif
static const u8 uac_it1[12]        = { 0x0c,0x24,0x02,0x01,0x03,0x06,0x00,UA_NCH,UA_CHCFG & 0xffu,UA_CHCFG >> 8,0x00,0x00 };
static const u8 uac_ot2[9]         = { 0x09,0x24,0x03,0x02,0x01,0x01,0x00,0x01,0x00 };
static const u8 uac_if3_alt0[9]    = { 0x09,0x04,0x03,0x00,0x00,0x01,0x02,0x00,0x00 };
static const u8 uac_if3_alt1[9]    = { 0x09,0x04,0x03,0x01,0x01,0x01,0x02,0x00,0x00 };
static const u8 uac_as_general[7]  = { 0x07,0x24,0x01,0x02,0x01,0x01,0x00 };
/* Type I format, 2 ch, 16 bit, the one rate as a continuous range 44100..44100
   (bSamFreqType 0): 14 bytes, so wTotalLength is 195. With one discrete rate it
   was 192 = 3 x 64, and a reply that is a multiple of EP0's 64 bytes, shorter
   than Windows' wLength 255, ends with the stock zero-length-packet path; after
   it the pedal STALLed SET_CONFIGURATION on a root port (Code 10, USB ETW trace
   2026-10-16, docs/CF_USB_MODE_2026-10-16.md). Keep wTotalLength % 64 != 0. */
static const u8 uac_format_i[14]   = { 0x0e,0x24,0x02,0x01,UA_NCH,0x02,0x10,0x00,0x44,0xac,0x00,0x44,0xac,0x00 };
static const u8 uac_ep1[9]         = { 0x09,0x05,0x81,0x05,UA_PKT_MAX & 0xffu,UA_PKT_MAX >> 8,0x01,0x00,0x00 };
static const u8 uac_cs_ep[7]       = { 0x07,0x25,0x01,0x00,0x00,0x00,0x00 };

#define DESC_COUNT 25   /* 24 populated + null terminator, recon/20 2.1 */

/* Writable: filled at init, not const storage (unlike the fragments it
   points into). Lives in .ua_state via the default (zero-init -> .bss,
   mapped to CTL2 in usb_audio.cmd) placement. */
const u8 *desc_ptrs[DESC_COUNT];

void usb_audio_build_descriptors(void)
{
    int i = 0;
    desc_ptrs[i++] = device_desc;
    desc_ptrs[i++] = new_config_hdr;
    desc_ptrs[i++] = stock_if0_ac;
    desc_ptrs[i++] = stock_ac_header;
    desc_ptrs[i++] = stock_if1_ms;
    desc_ptrs[i++] = stock_ms_header;
    desc_ptrs[i++] = stock_jack_in_emb;
    desc_ptrs[i++] = stock_jack_in_ext;
    desc_ptrs[i++] = stock_jack_out_emb;
    desc_ptrs[i++] = stock_jack_out_ext;
    desc_ptrs[i++] = stock_out_ep;
    desc_ptrs[i++] = stock_cs_ep1;
    desc_ptrs[i++] = stock_in_ep;
    desc_ptrs[i++] = stock_cs_ep2;
    desc_ptrs[i++] = uac_if2_ac;
    desc_ptrs[i++] = uac_ac_header;
    desc_ptrs[i++] = uac_it1;
    desc_ptrs[i++] = uac_ot2;
    desc_ptrs[i++] = uac_if3_alt0;
    desc_ptrs[i++] = uac_if3_alt1;
    desc_ptrs[i++] = uac_as_general;
    desc_ptrs[i++] = uac_format_i;
    desc_ptrs[i++] = uac_ep1;
    desc_ptrs[i++] = uac_cs_ep;
    desc_ptrs[i++] = (const u8 *)0;
}

/* Bounded CONFIGURATION-only copy into the stock reply buffer c0119fb0
   (as `out`), mirroring stock's min(total,
   host wLength) clipping (recon/17 B1 finding2: c013506c/70/76/80,
   c01350c6/ca) but with an explicit per-fragment bound against
   host_wlength and the explicitly supplied destination capacity. The pointer
   list includes device_desc at slot 0 for the stock walker; it is NOT part
   of the configuration response and must never be prepended here.
   Returns the byte count actually copied. Task context (called from the
   same control-request path as the stock clipping code). */
u32 usb_audio_copy_descriptors(u8 *out, u32 host_wlength, u32 out_capacity)
{
    u32 copied = 0;
    int i;

    if (out == (u8 *)0)
        return 0;
    if (host_wlength > out_capacity)
        host_wlength = out_capacity;

    for (i = 1; i < DESC_COUNT - 1 && desc_ptrs[i] != (const u8 *)0; i++) {
        const u8 *frag = desc_ptrs[i];
        u32 n = frag[0];      /* bLength is always the first byte */
        u32 j;

        if (copied >= host_wlength)
            break;
        if (copied + n > host_wlength)
            n = host_wlength - copied;

        for (j = 0; j < n; j++)
            out[copied + j] = frag[j];
        copied += n;
    }
    return copied;
}

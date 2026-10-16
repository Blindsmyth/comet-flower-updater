/* USB audio "silence stream" integration glue (OFFLINE candidate only).

   Wires firmware/usb_audio_proto/usb_audio.c into the stock USB stack per
   recon/20 2.6 (patch list v2) and recon/24 5.1:
     - IF2 (AudioControl) / IF3 (AudioStreaming) handler records, registered
       with c015afa0(6, &rec) right after usbmidi_open (hook at c0145158);
     - the IF3 SETUP callback handles SET_INTERFACE itself (design (b),
       recon/21 3.1) so stock c01212e0 never configures EP1 for CPPI DMA;
     - everything else falls through to the stock standard handlers.
   The slot->interface ownership map replacement for c015c66c is in
   ua_thunks.asm (it must keep the stock routine's register clobber set).

   Built only by tools/make_usb_audio_fw.py. DO_NOT_FLASH: no hardware test
   has validated any of this. */
typedef unsigned char u8;
typedef unsigned int u32;

#define STOCK_USBMIDI_OPEN ((int (*)(u32))0xc0152410u)               /* A4 = MIDI port callback */
#define STOCK_REGISTER     ((int (*)(u32, const void *))0xc015afa0u)  /* A4 = 6, B4 = record */
#define ALT_ARRAY          ((volatile u8 *)0xc011a1b0u)  /* c013596e (SET) / c0134e8c (GET) */
#define NOT_HANDLED 0xffff8a5bu   /* c01359e4 then falls through to the standard table */
#define REJECT      0xffff8a5cu   /* any other nonzero result STALLs EP0 (c0135ab4..c4) */
#define AS_INTERFACE 3u

/* USB-audio mode, at the fixed address c01a8000 (ua.cmd) so the controller
   payload can use it: {active, request, magic}. The controller writes only
   `request` (start-up button, settings page). `active` is copied from it
   once per USB open, in ua_usbmidi_open below, which stock runs on every
   full open (boot and cable attach: c016ab8c -> c016ab70 -> c0159758 ->
   c0145124 -> c0145158) before the device connects (c016ab80 -> c015af18,
   docs/helpers/USB_MODE_ASTRA_2026-10-16.md), so the descriptors and the
   registrations of one connection always agree. While `active` is 0 every
   patch behaves as stock: the descriptor veneer tail-branches to the stock
   builder for every type, IF2/IF3 are never registered, the map thunk runs
   the stock code, and no alternate is ever set (SOF tick and tap idle).
   `magic` tells the controller payload that this layer is present. The
   rest is read-only status for the settings page (first hardware run
   2026-10-16: request set, nothing new on Windows): open count, the two
   registration results of the last open (-1 = not attempted), and how
   often the host fetched a descriptor through our builder and set an IF3
   alternate while active. */
#define UA_MAGIC 0x41425355u      /* "USBA" */
typedef struct {
    volatile u32 active, request, magic;
    volatile u32 opens, reg[2], builds, set_alts;
} ua_mode_t;
#pragma DATA_SECTION(ua_mode, ".ua_mode")
ua_mode_t ua_mode = { 0u, 0u, UA_MAGIC, 0u, { 0xffffffffu, 0xffffffffu }, 0u, 0u };

/* Called by usb_audio_descriptor_veneer (usb_audio_hooks.asm) before it
   builds our device/configuration descriptor (active only). */
void ua_note_build(void)
{
    ua_mode.builds++;
}

extern int usb_audio_set_alt(u32 alt);
extern int ua_ep0_ack(void);                  /* ua_thunks.asm: c015af48(128, 0, 0) as c0151f5a */

int ua_ret0(void)
{
    return 0;
}


/* One record owns both audio interfaces (the stock registry takes only two
   records: c015c6b4 searches slots 0..1, `c015c718 MVK 2,A3`, and returns
   ffff8a5c at c015c744 otherwise; first hardware run 2026-10-16: IF3 was
   refused). The map thunk gives IF2 and IF3 to slot 1; the request is told
   apart by wIndex (SETUP byte 4, the interface for interface requests).
   IF2 (AudioControl, no controls): every request falls through to the stock
   standard handlers, as the MIDI callback does for non-standard types
   (c0151ed8..e4); stock SET_INTERFACE(IF2, 0) walks alt 0, no endpoints.
   IF3 (AudioStreaming): only standard SET_INTERFACE (bRequest 11) is ours.
   Record the alternate where stock GET_INTERFACE (c0134e68) reads it, then
   ACK the status stage. A4 = bmRequestType & 0x60, B4 = the 8-byte SETUP
   packet (c0135a52..a6c, recon/21 3.1). */
int ua_audio_request(u32 type, const u8 *setup)
{
    u32 alt;
    if (setup[4] != AS_INTERFACE || type != 0u || setup[1] != 11u)
        return (int)NOT_HANDLED;
    alt = (u32)setup[2] | ((u32)setup[3] << 8);
    if (usb_audio_set_alt(alt) != 0)
        return (int)REJECT;
    ALT_ARRAY[AS_INTERFACE] = (u8)alt;
    ua_mode.set_alts++;
    ua_ep0_ack();
    return 0;
}

/* Five-word records {+0, +4, +8 lifecycle, +12 SETUP callback, +16 endpoint
   hook}: recon/24 4.1 shows return-zero stubs are safe for +0/+4/+8/+16. */
typedef int (*ua_fn)(void);
#pragma DATA_SECTION(ua_audio_record, ".ua_state")
const ua_fn ua_audio_record[5] = { ua_ret0, ua_ret0, ua_ret0, (ua_fn)ua_audio_request, ua_ret0 };


/* Replaces c0145158 CALLP c0152410 (task context, before c015af18's
   soft-connect, recon/24 5.1). Registration order is an invariant: MIDI is
   slot 0, the audio record slot 1 (IF2 + IF3). reg[1] mirrors reg[0] (one
   registration) so the settings page's STAT reads ON only when it worked. */
int ua_usbmidi_open(u32 callback)
{
    int r;
    ua_mode.active = ua_mode.request ? 1u : 0u;
    ua_mode.opens++;
    ua_mode.reg[0] = ua_mode.reg[1] = 0xffffffffu;
    r = STOCK_USBMIDI_OPEN(callback);
    if (r == 0 && ua_mode.active) {
        ua_mode.reg[0] = (u32)STOCK_REGISTER(6u, ua_audio_record);
        ua_mode.reg[1] = ua_mode.reg[0];
    }
    return r;
}

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

extern int usb_audio_set_alt(u32 alt);
extern int ua_ep0_ack(void);                  /* ua_thunks.asm: c015af48(128, 0, 0) as c0151f5a */

int ua_ret0(void)
{
    return 0;
}

/* AudioControl IF2: no controls. Every request falls through to the stock
   standard handlers, exactly as the MIDI callback does for non-standard
   types (c0151ed8..e4). Stock SET_INTERFACE(IF2, 0) then walks alt 0, which
   has no endpoints. */
int ua_if2_request(u32 type, const u8 *setup)
{
    (void)type;
    (void)setup;
    return (int)NOT_HANDLED;
}

/* AudioStreaming IF3: only standard SET_INTERFACE (bRequest 11) is ours.
   Record the alternate where stock GET_INTERFACE (c0134e68) reads it, then
   ACK the status stage. A4 = bmRequestType & 0x60, B4 = the 8-byte SETUP
   packet (c0135a52..a6c, recon/21 3.1). */
int ua_if3_request(u32 type, const u8 *setup)
{
    u32 alt;
    if (type != 0u || setup[1] != 11u)
        return (int)NOT_HANDLED;
    alt = (u32)setup[2] | ((u32)setup[3] << 8);
    if (usb_audio_set_alt(alt) != 0)
        return (int)REJECT;
    ALT_ARRAY[AS_INTERFACE] = (u8)alt;
    ua_ep0_ack();
    return 0;
}

/* Five-word records {+0, +4, +8 lifecycle, +12 SETUP callback, +16 endpoint
   hook}: recon/24 4.1 shows return-zero stubs are safe for +0/+4/+8/+16. */
typedef int (*ua_fn)(void);
#pragma DATA_SECTION(ua_if2_record, ".ua_state")
const ua_fn ua_if2_record[5] = { ua_ret0, ua_ret0, ua_ret0, (ua_fn)ua_if2_request, ua_ret0 };
#pragma DATA_SECTION(ua_if3_record, ".ua_state")
const ua_fn ua_if3_record[5] = { ua_ret0, ua_ret0, ua_ret0, (ua_fn)ua_if3_request, ua_ret0 };

#pragma DATA_SECTION(ua_reg_result, ".ua_state")
volatile u32 ua_reg_result[2] = { 0xffffffffu, 0xffffffffu };

/* Replaces c0145158 CALLP c0152410 (task context, before c015af18's
   soft-connect, recon/24 5.1). Registration order is an invariant: MIDI is
   slot 0, IF2 slot 1, IF3 slot 2. If IF2 fails, IF3 is not attempted, so a
   later slot can never take IF2's place. */
int ua_usbmidi_open(u32 callback)
{
    int r = STOCK_USBMIDI_OPEN(callback);
    if (r == 0) {
        ua_reg_result[0] = (u32)STOCK_REGISTER(6u, ua_if2_record);
        if (ua_reg_result[0] == 0u)
            ua_reg_result[1] = (u32)STOCK_REGISTER(6u, ua_if3_record);
    }
    return r;
}

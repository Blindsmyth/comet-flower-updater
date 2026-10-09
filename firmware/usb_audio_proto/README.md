# USB audio "silence stream" prototype (not wired in)

Compiled-only prototype from round 4 (Helper B). The design, the patch list and the
open hardware questions are in recon/20_usb_audio_proto.md. Placement: SDRAM
c01a8000..c01affff. It is not part of any firmware image yet; it is
integrated only after the controller firmware passes a pedal test. The recon/21 3.3
fixes are in (keep MODE in every TXCSR write, clear stock's DMA bits on alt 1
in `usb_audio_set_alt`, SOF Hwi uses the direct EP1 TXCSR 0x01e00512 and no
INDEX).

# USB audio "silence stream" prototype (not wired in)

Compiled-only prototype from round 4 (Helper B). The design, the patch list and the
open hardware questions are in recon/20_usb_audio_proto.md. Placement: SDRAM
c01a8000..c01affff. It is not part of any firmware image yet; it is
integrated only after the controller firmware passes a pedal test. Known caveat
(recon/20 review): use the direct EP1 register block from the SOF Hwi
rather than the shared INDEX register.

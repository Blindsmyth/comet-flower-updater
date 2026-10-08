# Chunk 01 function map: 118072ac..1180b020

Summary: this range is the L2 (0x1180xxxx) task/driver region covering the
switch and knob input subsystems (normal-speed 10-button GPIO sampler and
its debounce/remap path, the two-footswitch sampler, the four-knob relative
encoder/accumulator path), the AD task's external serial converter read
(GPIO-bit-banged handshake plus i2c_write), the McASP/EDMA audio-engine
builder and ISR dispatch, the zero-target gain-ramp family, MIDI compose/
queue helpers shared with MainApp, LooperUI mute-group helpers, UpdateUI
screen-list/scroll helpers, and a block of small MainApp/UI orchestrators
entered through the c016e020/c016e000 save-restore pair. Most routines in
the low 1180axxx addresses are thin leaves or glue with few or no internal
branches; call-graph position and B14 slot reuse are the main evidence for
those, so many rows below are "likely" rather than "confirmed". Three
functions in this range are already named in recon/map/00_library_kernel.md
and are skipped here (see 00): 118093c0, 1180a2a8, 1180ad68.

| addr | name | role | conf | evidence |
|---|---|---|---|---|

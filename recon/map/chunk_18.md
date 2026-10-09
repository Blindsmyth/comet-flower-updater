# chunk_18: c016e020..c016ec40 (68 functions)

Summary: Mapping in progress.

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| c016e020 | rts_regs_save | save ABI-preserved registers on the stack and return through A3 | confirmed | c016e020 `STW B14,*B15--[2]`; c016e024 `B A3` with delay slots storing A15:A10, B13:B10, and B3:B2 |
| c016e0c0 | runtime_global_3aec_set | store A4 to runtime global c0183aec | confirmed | c016e0c4-c016e0cc form c0183aec and `STW A4,*A3` in the return delay slots |
| c016e100 | stack_pointer_init_if_zero | conditionally initialize B15 from runtime global c0181fcc | confirmed | c016e100 copies A4 to B0; A4!=0 -> return/no writes; A4==0 -> c016e110 loads B15 from c0181fcc and c016e114 clears that global |
| c016e120 | runtime_halt | spin forever | confirmed | c016e124 `BNOP 0xc016e124,5` |
| c016e140 | callback_broadcast_null | broadcast a null event/value tuple | confirmed | c016e140 saves B3; c016e144 calls `callback_broadcast_tailcall` with B4=0, A6=0, then returns A4=0 |
| c016e160 | codec_init_default_device | initialize codec using descriptor at ffffac44 | confirmed | c016e164/c016e16c load A4=ffffac44; c016e168 calls `codec_init_and_mute` |
| c016e180 | variant_record_copy_adapter | rearrange an encoded record and tail-call variant-record copy | likely | c016e180/c016e188 load A6 from original A4+3; c016e18c-c016e194 pass A4=old B4 and B4=old A4+7; c016e184 branches to `variant_record_copy` |
| c016e1a0 | audio_ramp_table_apply_mode1 | apply the audio ramp table with mode 1 | confirmed | c016e1a0 preserves B3 in A2; c016e1a4 calls `audio_ramp_table_apply` with A6=1; c016e1ac returns through A2 |
| c016e1c0 | int32_to_float | convert signed integer A4 to single-precision float | confirmed | c016e1c0 `INTSP A4,A4`; c016e1c4 returns |
| c016e1e0 | audio_ramp_callback_invoke_zero | invoke the installed audio-ramp callback with A4=0 | confirmed | hidden start; c016e1e4 calls c016e2c0 with c016e1e8 `MVK 0,A4` |

## Data


## Open questions

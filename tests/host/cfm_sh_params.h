/* cfm_sh_params.h - Host mock parameters for CF Master */
#ifndef CFM_SH_PARAMS_H
#define CFM_SH_PARAMS_H

#ifdef __cplusplus
extern "C" {
#endif

#define SH_AUDIO_FN Fx_SFX_CFMASTER
void Fx_SFX_CFMASTER(void **instance, void **ctx);

#define SH_FRAMES        16
#define SH_CH_B_OFFSET   16
#define SH_COEFF_BYPASS  0

#define SH_CTX_GTRIN     0
#define SH_CTX_EFF       1
#define SH_CTX_OUT       2
#define SH_SAMPLE_RATE   44100.0f
#define SH_STATE_BYTES   392

#define SH_STATE_GUARD       0x57464731u
#define SH_STATE_GUARD_WORD  16

#define SH_NUM_PARAMS        12
#define SH_PARAM_MUFF_SUST   1
#define SH_PARAM_MUFF_TONE   2
#define SH_PARAM_MUFF_VOL    3
#define SH_PARAM_MIST_RATE   4
#define SH_PARAM_MIST_COLOR  5
#define SH_PARAM_DLY_TIME    6
#define SH_PARAM_DLY_MIX     7
#define SH_PARAM_AMP_DRIVE   8
#define SH_PARAM_AMP_MASTER  9
#define SH_PARAM_ROTOR       10
#define SH_PARAM_ROT_SPEED   11
#define SH_PARAM_RIG_BLEND   12

#ifdef __cplusplus
}
#endif

#endif /* CFM_SH_PARAMS_H */

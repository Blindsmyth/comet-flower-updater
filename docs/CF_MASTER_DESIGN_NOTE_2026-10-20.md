# CF Master design note (owner, 2026-10-20)

Recorded before the Updater 25 flash. The owner's questions to answer after the Updater 25 results are still to be added.

## Concept
- CF Master is **one effect that occupies all 5 slots**, so it is the only effect that can be loaded in a patch.
- **Each page of the effect holds the settings for one stage of the effect chain.** The chain models the Comfortably Numb rig.
- Stage order, as built so far: DynaComp -> Big Muff -> Electric Mistress -> Delay -> Hiwatt (Watt) amp -> RA-200 (rotary/chorus).

## Requirement for the DSP
- Each stage must be **modified and streamlined so the signal flows correctly end to end**. This includes gain staging and headroom between stages.
- Every stage must be **fully adjustable from its own page**.
- Every stage page needs its own **On/Off switch**. Example: the chorus page has an off switch, so the chorus can be bypassed without affecting the rest of the chain.
  - Bypass must be click-free.
  - When bypassed, a stage should cost ~0 cycles where possible, which helps the dspload budget.

## Open (depends on Updater 25 results)
- Do `CFM2P`/`CFM5P` show that multi-slot effects get more memory? If yes, the 5-slot monolith can load. If no, deduplicate code across stages or split the chain.
- Measured cycle counts per stage, to be fed into `zd2_set_dspload.py`.
- The owner's follow-up question(s) after Updater 25 are still to be recorded here.

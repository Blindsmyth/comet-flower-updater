# S8 - Slot occupancy of multi-slot effects

## Status
running

## Findings

### Finding 1: Per-slot patch record effect ID 1 (filler) store and compare sites (confirmed)
In Zoom G1 FOUR patch data (see `tools/g1presets.py` and factory patches `PATCH_001.ZPTC`..`050.ZPTC`), multi-slot effects occupy the primary slot plus consecutive filler slots. In storage, the filler slot has:
- PTCF 5-entry `ids` array (offset 36 in patch header): `0x00000001`
- EDTB 24-byte slot entry: word 0 is `0x00000003` (`(1 << 1) | 1`, on=1, 29-bit effect ID = 1), followed by 20 bytes of zero.
- In-memory per-slot working array: 84 bytes per slot (`0x54` stride) at `0x11811598`. Offset +0 is on/off (1=on), offset +4 (`0x1181159c + 84*slot`) is `effect_id` (1=filler).

Code in `main.dis` that stores or compares effect ID value 1:

#### Site 1 (Store): `c0132708` (`fxslot_insert_filler`) - CONFIRMED
Called by `c0132824` during slot insertion when expanding a multi-slot effect. It zeroes the 84-byte record at `0x11811598 + 84*slot` via `memset` (`c0167b00`), then stores `1` into `on` (word 0) and `1` into `effect_id` (word 1):
```assembly
c0132788   00002a2a           MVK.S2        0x0054,B0        ; B0 = 84 (0x54) stride
c013278c   00281572           MPYLI.M2X     B0,A10,B1:B0     ; B0 = 84 * slot (A10 = filler slot index)
c0132790       2426           MVK.L1        1,A0             ; A0 = 1
c0132792       2c6e           NOP           2
c0132794       e041           ADD.L2        B7,B0,B4         ; B4 = 0x11811598 + 84 * slot
c0132796       0005           STW.D2T1      A0,*B4[0]        ; *B4[0] = 1 (on/off flag = 1)
c0132798       8686           MV.L1         A13,A4           ; A4 = 0x11811598 + 84 * slot
c013279a       2004           STW.D1T1      A0,*A4[1]        ; *A4[1] = 1 (effect_id at offset 4 = 1!)
c013279c   ee600003           .fphead       n, l, W, BU, nobr, nosat, 1110011b
c01327a0   103dbf13           CALLP.S2      0xc0151598,B3
```

#### Site 2 (Compare): `c0130d50` (`fxslot_is_filler`) - CONFIRMED
Loads `effect_id` of slot `A4` from `0x1181159c + 84 * slot` and checks equality with 1:
```assembly
c0130d50   00002a28           MVK.S1        0x0054,A0        ; A0 = 84
c0130d54   03100570           MPYLI.M1      A0,A4,A7:A6      ; A6 = 84 * slot
c0130d58   000ace2a           MVK.S2        0x159c,B0
c0130d60   0008c0ea           MVKH.S2       0x11810000,B0    ; B0 = 0x1181159c (effect_id base)
c0130d64       2c6e           NOP           2
c0130d66       1341           ADD.L2X       B0,A6,B4         ; B4 = 0x1181159c + 84 * slot
c0130d68       100d           LDW.D2T2      *B4[0],B0        ; B0 = effect_id
c0130d6a       6c6e           NOP           4
c0130d6c   00003a58           CMPEQ.L1X     1,B0,A0          ; A0 = (effect_id == 1)
c0130d70       8046           MV.L1         A0,A4            ; return A4 = 1 if filler, else 0
c0130d72       a1ef           BNOP.S2       B3,5
```

#### Site 3 (Compare): `c0130d28` (`fxslot_is_empty_or_filler`) - CONFIRMED
Loads `effect_id` from `0x1181159c + 84 * slot`, clears bit 0, and tests if zero (true for 0=empty and 1=filler):
```assembly
c0130d28   00002a28           MVK.S1        0x0054,A0        ; A0 = 84
c0130d2c   03100570           MPYLI.M1      A0,A4,A7:A6      ; A6 = 84 * slot
c0130d30   000ace2a           MVK.S2        0x159c,B0        ; B0 = 0x1181159c
c0130d34   0008c0ea           MVKH.S2       0x11810000,B0
c0130d38       2c6e           NOP           2
c0130d3a       1341           ADD.L2X       B0,A6,B4         ; B4 = 0x1181159c + 84 * slot
c0130d40       100d           LDW.D2T2      *B4[0],B0        ; B0 = effect_id
c0130d42       6c6e           NOP           4
c0130d44       0043           CLR.S2        B0,0,0,B0        ; B0 = effect_id & ~1
c0130d48   00001a58           CMPEQ.L1X     0,B0,A0          ; A0 = ((effect_id & ~1) == 0)
c0130d4c       8046           MV.L1         A0,A4            ; return 1 if empty or filler
c0130d4e       a1ef           BNOP.S2       B3,5
```

#### Site 4 (Compare): `c01348d4..c0134918` (UI slot swap/move/delete refusal) - CONFIRMED
In UI slot manipulation dispatcher `c0134850`, before moving or swapping slots `A10` and `A11`, it calls `c0130d50` on each slot. If either is filler (`effect_id == 1`), it aborts:
```assembly
c01348d0       6646           MV.L1         A4,A11           ; A11 = target slot
c01348d2       8506           MV.L1         A10,A4           ; A4 = source slot
c01348d4   1ff89212 ||        CALLP.S2      0xc0130d50,B3    ; fxslot_is_filler(source)
c01348d8       0246           MV.L1         A4,A0
c01348da       af2a    [ A0]  BNOP.S1       0xc0134938,5     ; source is filler -> ABORT
c01348dc   ea408200           .fphead       n, l, W, BU, br, nosat, 1010010b
c01348e0   1ff88e13           CALLP.S2      0xc0130d50,B3    ; fxslot_is_filler(target)
c01348e4       8586 ||        MV.L1         A11,A4
c01348e6       0246           MV.L1         A4,A0
c01348e8       ab2a    [ A0]  BNOP.S1       0xc0134938,5     ; target is filler -> ABORT
c01348f4   10276513           CALLP.S2      0xc0148408,B3    ; safe -> perform swap
```

#### Site 5 (Compare): `c0147fc0` (`fxslot_count_active_between`) - CONFIRMED
Counts non-filler active effects between two slot positions, skipping slots with `effect_id == 1`:
```assembly
c0147fe6       d040           ADD.L1X       A6,B0,A4         ; A4 = 0x1181159c + 84 * slot
c0147fe8   000c30fa           SUB.L2X       B1,A3,B0         ; loop count
c0147fec   0012b664           LDW.D1T1      *A4++[21],A0     ; A0 = effect_id, step 84 B
c0147ff0       2026           CMPEQ.L1      1,A0,A0          ; A0 = (effect_id == 1)
c0147ff2       a2ea    [ A0]  BNOP.S1       0xc0147ff6,5     ; if filler, skip increment
c0147ff4       2490           ADD.L1        A1,1,A1          ; non-filler -> count++
c0147ff6       ec01           ADD.L2        B0,-1,B0
c0147ff8   2006a120    [ B0]  BNOP.S1       0xc0147fec,5
c0147ffc   e6508000           .fphead       p, l, W, BU, br, nosat, 0110010b
c0148000       00c6           MV.L1         A1,A0            ; return non-filler count
```

#### Site 6 (Compare): `c0148008` (`fxslot_find_master`) - CONFIRMED
Given a slot index `A4`, loops backwards as long as `effect_id == 1` to find the primary (master) effect slot:
```assembly
c0148020   0008c0ea           MVKH.S2       0x11810000,B0    ; B0 = 0x118115f0 (slot 1 effect_id base)
c0148024       0c6e           NOP           1
c0148026       d040           ADD.L1X       A6,B0,A4         ; A4 = slot pointer
c0148028   00041fda           MV.L2X        A1,B0            ; B0 = current slot
c014802c   0012b064           LDW.D1T1      *--A4[21],A0     ; load previous slot effect_id
c0148030       2026           CMPEQ.L1      1,A0,A0          ; is previous slot a filler?
c0148032       a43a    [!A0]  BNOP.S1       0xc0148040,5     ; not filler -> found master!
c0148034       ec90           ADD.L1        A1,-1,A1         ; decrement master slot index
c0148036       ec01           ADD.L2        B0,-1,B0
c0148038   2006a120    [ B0]  BNOP.S1       0xc014802c,5     ; loop backward while filler
```

#### Site 7 (Compare): `c0148354` (`fxslot_find_next_effect`) - CONFIRMED
Given a slot index `A4`, loops forward past consecutive filler slots (`effect_id == 1`) to find the next distinct effect:
```assembly
c0148380   0580d078           ADD.L1X       A6,B0,A11        ; A11 = 0x1181159c + 84 * slot
c0148384   022c0fd8           MV.L1         A11,A4
c0148388   0012b264           LDW.D1T1      *++A4[21],A0     ; load next slot effect_id
c014838c       6646           MV.L1         A4,A11
c014838e       4c6e           NOP           3
c0148390       2026           CMPEQ.L1      1,A0,A0          ; is next slot a filler?
c0148392       a4fa    [!A0]  BNOP.S1       0xc01483a6,5     ; not filler -> found next!
c0148394   1fefdb12           CALLP.S2      0xc0140258,B3
c0148398   05282058           ADD.L1        1,A10,A10        ; advance slot index
```

#### Site 8 (Compare): `c013ba64` (`fxslot_count_following_fillers`) - CONFIRMED
Counts how many consecutive filler slots follow slot `A4`:
```assembly
c013baa8       d080           ADD.L1X       A6,B1,A0
c013baaa       1940           SUB.L1X       A0,B2,A4         ; A4 = slot pointer
c013baac   000c10fa           SUB.L2X       B0,A3,B0         ; remaining slots in patch
c013bab0   0012b264           LDW.D1T1      *++A4[21],A0     ; load next slot effect_id
c013bab4       2026           CMPEQ.L1      1,A0,A0          ; effect_id == 1?
c013bab6       a4ba    [!A0]  BNOP.S1       0xc013bac4,5     ; not filler -> stop
c013bab8       2490           ADD.L1        A1,1,A1          ; count++
c013baba       ec01           ADD.L2        B0,-1,B0
c013babc   ecd08000           .fphead       n, l, W, BU, br, nosat, 1100110b
c013bac0   2ff8a120    [ B0]  BNOP.S1       0xc013bab0,5     ; loop
```

### Finding 2: Fate of the slot-count header byte (header 0x58) after c0129908 (confirmed)
The ZD2 header copy resides at stack offset `B15+40`. Header offset `0x58` (88 decimal) is at `B15+40+88 = B15+128` (`*+B15[128]`).

Across the entire firmware, exactly three loads of `*+B15[128]` exist, all in `effect_slot_load_unload` (`c01297a0`):

1. **Ceiling check (`c0129904`) - CONFIRMED:**
   ```assembly
   c0129904   0000809e           LDBU.D2T2     *+B15[128],B0    ; B0 = header byte 0x58
   c0129908   00008bda           CMPLTU.L2     0x4,B0,B0        ; B0 = (4 < B0)
   c012990c   2120a120    [ B0]  BNOP.S1       0xc0129b40,5     ; reject if B0 > 4
   ```
   If header 0x58 is 5, it branches to `c0129b40` (load error/rejection). Thus header 5 is never added to the effect catalog.

2. **Unused argument to loader (`c0129a6c`) - CONFIRMED:**
   ```assembly
   c0129a64       cc5b           CALLP.S2      0xc0129724,B3    ; install slot resources
   c0129a6c   0300809e ||        LDBU.D2T2     *+B15[128],B6    ; B6 = header byte 0x58
   ```
   `c0129724` accepts arguments in `A4`, `B4`, `A6`, `B6`. Tracing all instructions inside `c0129724` (`c0129724..c0129798`) confirms register `B6` is **never read or stored**. It allocates single-slot heap and state based solely on scalar slot index `A11`.

3. **Storage into effect catalog table (`c0129ab4`) - CONFIRMED:**
   ```assembly
   c0129ab0   00148a34           STB.D1T1      A0,*+A5[A4]
   c0129ab4   0000809c           LDBU.D2T1     *+B15[128],A0    ; A0 = header byte 0x58
   c0129ab8   02229428           MVK.S1        0x4528,A4
   c0129abc   e1000000           .fphead       n, l, W, BU, nobr, nosat, 0001000b
   c0129ac0   02600368           MVKH.S1       0xc0060000,A4    ; A4 = 0xc0064528
   c0129ac6       8684           STB.D1T1      A0,*A5[A4]       ; 0xc0064528[catalog_idx] = 0x58
   ```
   The slot-count byte is stored in a byte table at `0xc0064528 + catalog_idx`. (On error/fallback paths, it is forced to 1 at `c0129b86`, `c0129c64`, `c0129d12`).

4. **Access to `0xc0064528` and the hardcoded UI stub - CONFIRMED:**
   The byte table at `0xc0064528` is accessed by:
   - `c0129680` / `c0129698`: shifts entries during catalog add/remove.
   - `c012b260(effect_id)`: searches `0xc0064f6c` for `effect_id` and reads `0xc0064528[catalog_idx]`. Called by `c013b690` and `c013b8c0`.
   
   **CRUCIAL FINDING**: In the pedal UI effect picker (`c0132658`), slot inserter (`c01327c8`), and effect replacer (`c0133254`), the firmware does NOT call `c012b260`. Instead, it calls `c012b2c0` and `c012af98`:
   ```assembly
   c012b2c0       2626           MVK.L1        1,A4             ; HARDCODED RETURN 1!
   c012b2c2       a1ef           BNOP.S2       B3,5
   ...
   c012af98       2626           MVK.L1        1,A4             ; HARDCODED RETURN 1!
   c012af9a       a1ef           BNOP.S2       B3,5
   ```
   Both functions unconditionally return constant `1`. Consequently:
   - `c0132658` evaluates candidate effect width as 1 for every effect.
   - `c01327c8` computes `new_width - old_width = 1 - 1 = 0`, bypassing the filler insertion loop at `c0132824`.
   - The parsed header byte 0x58 stored at `0xc0064528` is completely bypassed by the pedal UI slot management. Every effect is treated as 1 slot.



## Answers

## Not checked / open leads

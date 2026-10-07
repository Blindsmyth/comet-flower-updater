# Effect memory map - firmware map part 2

Static analysis of res1_493412.bin, 2026-10-06. No pedal access. Confidence labels describe static evidence, not measured runtime addresses. Only this report and build/codex3 are edited. PowerShell/.NET readers are used because the hard rule forbids running python.exe as well as other executables except dis6x.

> **CONFIRMED ON THE PEDAL (2026-10-06, CF MEMPRB, VPB_2026-10-06_212158).**
> Decoded (magic + XOR check OK): code 0xc01fe1e0 and const_blob 0xc01fecb8
> inside the slot-1 region 0xc01fe000+0xa000 (SDRAM, cached); state
> 0x11f01650, knob table 0x11f00348, instance 0x11f03ae4, audio bus
> 0x11f037b0, all exactly Codex's slot-1 values (L1D RAM); stack 0x11816140
> (L2 RAM). Slot numbering: the probe sat in the pedal's slot 2, so the
> firmware's slot index is 0-based (pedal slot N = index N-1). Timings: 128 strided const_blob reads cost 64.2 cycles/read on
> the first call (cold SDRAM) and 5.1 at later frame starts, the same as
> on-chip stack reads (5.2, which is the timing loop's own latency): after
> first use the table is served from cache. So steady-state table reads do
> NOT explain the ~1.5x gap of CF RAT / CF 808; the next suspect is code
> refetch (L1P eviction by firmware work between blocks).
>
> **Review by Claude (2026-10-06).** Written by Codex (gpt-6-astra, medium)
> from docs/helpers/CODEX_LOADER.md. Evidence is instruction-level and the
> parts Claude checked hold. It corrects recon/06 and recon/13: entry
> [5]-[8] are callbacks, not memory requests. **To be confirmed on the
> pedal** by CF MEMPRB (effects/memprobe, tools/decode_memprobe.py), which
> reports its own addresses. Predictions for an effect in slot n (0-based):
> code and const_blob inside 0xc01f4000 + n*0xa000 (40 KiB, SDRAM, cached via
> MAR192); state = 0x11f013b0 + n*0x2a0 (L1D RAM); knob table =
> 0x11f00000 + n*0x348 (L1D RAM); audio buffer = 0x11f037b0 (L1D RAM).
> Consequences if confirmed: our tables are read from cached SDRAM (cold
> misses are slow; the 16 KB L1D cache is shared by all slots), while state
> lives in the fastest memory, and the per-slot state area is 672 B, not
> 392 B.

**Result (confirmed for the traced five-slot loader):** effect .text/.const and PT_LOAD zero-fill storage use fixed 40 KiB SDRAM regions. MAR192 makes those regions cacheable at startup. Framework coefficient/state buffers and the shared audio bus are L1D RAM. The alleged entry[5]-[8] size requests are actually callbacks; the recon/13 allocator trace concerns ELF symbol metadata.
## 1. Effect image placement
**Confirmed:** ZDLF scanning compares the signature at c017f598 in c012988c..98ac. ELF magic checking starts at c0123478 (127, then 69='E'). The generic ELF loader entry is c0124b2c. Its calls include parse c01233c0/c0123620, module creation c0123ce4, segment loading c01242bc. Relocation dispatch reaches c0133f28, detailed below; c0124584 instead looks up a special symbol.

**Confirmed:** c01560f0 takes source-image descriptor A4 and destination-region descriptor B4. It copies destination [0]/[1] to a temporary file descriptor's [3]/[4] (c0156170..6176), then calls c0124b2c at c015618c. c015fe64 reads those [3]/[4] as region base/size, initializes a heap with c0150f20, allocates 132 bytes and copies the 36-byte heap object to module+96.

**Confirmed:** c0129724 is one effect-facing caller; its destination base and size come from c0164a8c and c0164a80 with slot/index A11. Their decoded tables are listed below. Another loader caller c014f284 supplies SDRAM directly:
```text
c014f298 MVK 0x2800,B1
c014f2a0 SHL A0,0xd,A0
c014f2a4 SHL A1,0xf,B0
c014f2a8 MVKH 0xc00d0000,B1
c014f2ac ADD B0,A0,B0
c014f2ae ADD B1,B0,B0
c014f2b0 STW B0,*B15[3]     ; base=c00d2800+index*0xa000
c014f2b2 MVK 5,A0
c014f2b4 SHL A0,0xd,A0
c014f2b6 STW A0,*B15[4]     ; size=0xa000 (40 KiB)
c014f2cc CALLP c01560f0
```
**Confirmed:** loaded segments share module+96's heap; no fast-memory selection by section name established. In c01242bc, a 48-byte internal record is built from a 32-byte ELF program header (PT_LOAD test c0123e44..4a). c0124368 calls c015f72c with A4=module+96, request flags=(segment flags &1)|2, alignment=32. c015f72c calls c0163af4 -> c0163ac0 -> c0151190 allocator. c0163b12..28 tests request bit 1 and uses address -1 to request allocation; c0163b2e loads segment memory size from descriptor[3]. c015f780 zeroes the segment memory, then c015f7a4 reads file bytes. Thus allocation follows loadable segments, not separate .text/.const/.bss names. The NYC cross-check below confirms two PT_LOAD segments containing .text and .const.

**Confirmed:** c0146cb4 is symbol/string copying, not effect work-memory allocation. It obtains the module from parser-object[27] (c0146cc0), copies 16-byte symbol records (c0146d30), and rebases their name pointers (c0146e00..0c). c0146a60 reads symbol info byte 12, section-index bytes 14/15, value word 1 and advances by 16.

### Slot image regions recovered from C initialization
**Confirmed:** c0164a8c indexes base table c01839a8; c0164a80 indexes size table c01839c0. Decoded initial values for slots 0..4 are:

| Slot | Module heap backing base | Size |
|---|---|---|
| 0 | c01f4000 | a000 (40 KiB) |
| 1 | c01fe000 | a000 |
| 2 | c0208000 | a000 |
| 3 | c0212000 | a000 |
| 4 | c021c000 | a000 |

All are SDRAM within cacheable MAR192. These are fixed per-slot image regions; allocator packing determines segment addresses inside them. The 40 KiB includes module bookkeeping and allocator overhead, not just .text. There is no demonstrated size-triggered spill to SDRAM: the caller supplies SDRAM from the outset.

Reproducible evidence: startup c0163708..3728 sets handler table c0186ddc and record range c0186ef4..c0187024. c0163772 reads handler byte, c0163780 indexes handler, c0163788 calls it. First record maps compressed c0185260 to c0181b28. Handler 1 is c016e1a0 -> c0161e60 (escape/run decoder); handler 0=c0167860 zero-fill; handler 2=c016e180 raw copy. build/codex3/decode_cinit.ps1 reconstructs the regions; build/codex3/initwords.ps1 prints their words. Output includes c01839a8=c01f4000 and c01839c0=0000a000. Record c0186e44 -> c01f4000 independently zeroes a000 bytes. Decoded sizes and consumed source lengths terminate within the next record; raw initialized tables are not present at their runtime addresses in AIS, explaining why a direct words lookup misses them.

### Relocation implementation (confirmed)
The machine-handler table at c0183688 starts with EM_C6000=0x8c and has relocation handler c0133f28 at word[4]. c01235ec selects it, c0123648 stores it at B14[132], and c0122d50 calls its word[4]. Load chain: c0124b2c -> c0124974 -> c012484c -> c0122d50 -> c0133f28. The handler reads DT_RELA/DT_REL information, then c0133d38 dispatches the RELA loop c0133a98 or REL loop c0133be8. RELA evidence:
```text
c0133b16 LDNW *A4[1],A0        ; r_info
c0133b18 EXTU A0,24,24,A1      ; low 8-bit relocation type
c0133b28 SHRU A0,8,A0          ; symbol index
c0133b30 CALLP c0146e18        ; resolve symbol
c0133b58 LDNW *A7[2],A6        ; explicit addend
c0133b74 CALLP c013398c        ; evaluate and apply relocation
c0133b98 ADD 12,A11,A11        ; next Elf32_Rela
```
c013398c computes S+A for the absolute types (c0133a20), then calls overflow/shift/mask helpers and patcher c01337f8. Its jump table c01841ec selects type 1 -> c013396e `STW B1,*B5[0]` (ABS32); type 9 -> c01338d6, shifting value left 7, clearing instruction bits 7..22, OR and store at c01338ea (ABS_L16); type 10 -> c01338c2, same instruction-field insertion/store at c01338d2 after c0133670 selects c0133704/c0133708 to shift the value right 16 (ABS_H16). c0133978 calls cache-operation wrapper c016e380 after patching. Stock NYC has 9 type-1, 12 type-9, 12 type-10 relocations, independently parsed by build/codex3/elf.ps1.

NYC program headers independently confirm .text is PT_LOAD at original vaddr 0, size 0x1220, flags 5; .const is PT_LOAD at original vaddr 0x80000000, size 0x6f8, flags 4. These original ELF virtual addresses are NOT runtime memory regions. Both go through the same per-module SDRAM allocator. NYC .bss is empty. Nonempty zero-fill storage inside PT_LOAD is covered by the loader's full-memsz memset followed by filesz read; arbitrary non-loadable .bss is not thereby allocated.

## 2. Heaps
**Confirmed:** custom region heap initializer c0150f20; allocator c0151190, default-alignment wrapper c015f644; free c01510e8. Heap object is 36 bytes. Initializer records supplied base and byte size:
```text
c0150f84 STW B0,*A4[0]     ; original base
c0150f88 STW A0,*A4[1]     ; original size
c0150f90 STW B0,*A4[2]     ; aligned base
c0150f98 STW B0,*A4[3]     ; usable size rounded down to 8
c0150fa0 STW A0,*A4[4]     ; free-list head
c0150fb6 SUB A0,8,A0
c0150fb8 STW A0,*A4[1]     ; A4 now free-block header: payload size
```
The module's embedded heap is +96 bytes. This offset itself says nothing about L2 versus SDRAM. The additional heap configurations below are separate from this custom allocator. Generic HeapMem/HeapBuf strings alone are insufficient evidence of an instance.

| Region / instance | Backing base | Capacity | Allocator / provisioning |
|---|---|---|---|
| Five effect module heaps | c01f4000 + slot*0xa000 | 0xa000 each | c0151190; wrapper c015f644; segment path c015f72c |
| Alternate image-loader region | c00d2800 + index*0xa000 | 0xa000 each | Same custom module heap; role of caller unresolved |
| Static HeapMem-family instance c0183a08 | c00f1800 | 0x8000 | c0143f60; free c0143900 |
| Loader-support handle B14[115] | c0184a00 | 0x400 | c0143f60 via c0163118; free via c01630b4 |
| Per-slot coefficients | See section 4 | 0x348 each | Fixed storage, no allocation call |
| Per-slot state | See section 4 | 0x2a0 each | Fixed storage, no allocation call |
| Per-slot large work buffers | See below | 0x81330 each | Fixed descriptor, no general allocator established |

The custom allocator uses byte counts, rounds payload size to 8 bytes, has an 8-byte allocation header, and segment requests specify 32-byte alignment. c01511f8..c0151244 searches the free list; c0151274/c01512b0 reports failure if no suitable block exists. Its limit is available contiguous space in the supplied region, including headers/alignment/other module allocations; no L2-to-SDRAM fallback was found in this path.
### Additional heap finding (confirmed backing; HeapMem identification likely)
c0163040 initializes a 0x400-byte heap at c0184a00: c0163066..306a forms 1<<10 and stores params size; c016306c..3074 forms c0184a00 and stores params buffer; c0163078 calls constructor c016b440; c0163094 saves handle at B14[115]. c016b440 uses module descriptor c0180e20 and calls c0162760 to initialize its instance. c0162766 loads params buffer, c0162794 stores instance[2], c016279c loads params size, c01627d8 stores instance[4]. Wrapper c0163118 allocates request+4 bytes, alignment 4, via c0143f60 and stores the length before the returned pointer; free c01630b4 calls c0143900. This is a separate loader-support heap, not the per-effect image region. Full SYS/BIOS static-instance enumeration is still open.

**Confirmed static heap configuration:** c0183a08 is an instance with vtable c0180848; its buffer c0183a10=c00f1800 and byte size c0183a18=0x8000 (32 KiB). That vtable has alloc c0143f60 at +8, free c0143900 at +12, getStats c0168dc0 at +20; constructor table c0180860 contains c016b440. Instance layout is proved by constructor c0162766/c0162794 (buffer -> instance[2]), c016279c/c01627d8 (size -> instance[4]), and stats c0168dd8/c0168df0 (instance[4] -> total size), with a free-list walk from instance[3]. Thus both the static 32 KiB heap and dynamically constructed 1 KiB loader-support heap use this allocator family (likely SYS/BIOS HeapMem). Static scan found one initialized instance of this vtable; it does not exclude dynamically created instances.

**Confirmed additional fixed buffers:** instance[3] points to a 12-byte descriptor in c0183470+12*slot (c014febc/c014fec8 form table, c014feec stores descriptor at instance+12, c014fef8 advances by 12). Descriptors are {base,end,size}: bases c0226000,c02a7330,c0328660,c03a9990,c042acc0; each size 0x81330 bytes. c0164a98..c0164b24 explicitly zeroes each base for 0x81330 bytes. These are large SDRAM work buffers, not evidence of a general L2 heap. An additional descriptor at c01834ac covers c04abff0..c075d0f0, size 0x2b1100; its effect ownership is not established.

## 3. Fields [5]-[8]
**Confirmed major correction to recon/06 AND recon/13: actual Dll entry[5]..[8] are callback pointers, not allocation-size requests.** c012b030 returns `c0064410 + slot*36`, i.e. entry+16. The entry base is c0064400+36*slot; c0129d80..9daa clears optional entry[4]..[8] before the indirect Dll entry call. The framework reads its words [1],[2],[3],[4] (=entry[5],[6],[7],[8]) and branches to the resulting value:

| Entry field | Firmware evidence | Meaning established |
|---|---|---|
| [5] | c0143254 calls c012b030; c0143258 LDW *A4[1],A0; c0143294 B.S2X A11 | callback with instance A4, service ctx B4 |
| [6] | c0143738 calls c012b030; c0143744/c0143766 LDW *A4[2],A0; c014376c B.S2X A0 | callback with instance A4, service ctx B4 |
| [7] | c0167520 calls c012b030; c0167526 LDW *A4[3],A0; c0167568 B.S2X A11 | callback invoked by background loop |
| [8] | c01433f8 calls c012b030; c0143400 LDW *A4[4],A0; c0143404 B.S2X A0 | callback, three arguments forwarded |

No byte/word/sample unit, allocation alignment, heap limit or returned buffer applies to these pointer fields. Writing 8192 into entry[5] would install a function address, not request an 8 KiB table. Function purpose beyond the call sites should not be inferred from a numeric value.

Stock cross-check: extracted HALL.ZD2 DATA to build/codex3/HALL.elf, disassembled with the explicitly permitted dis6x. Dll_Hall at .text+df0 sets A2=0x8d8 using MVKL/MVKH at e0c/e10 and stores it to entry[5] at e16. This is the .text address of Fx_REV_Hall_tapmuteMute (symbol and code at 0x8d8), not the integer 2264-byte request claimed in recon/06. At 8d8 it loads instance[1]; at 8da it loads service ctx[3]; at 8f4 it calls that service. NYC Muff Dll at .text+11c0 writes only entry[0],[1],[3] and makes no such request.

**Confirmed correction to recon/13:** at c0146ce4 these are module bookkeeping, not the stock effect entry. Module[5]=symbol-array pointer; [6]=symbol count; [7]=string-storage pointer; [8]=string-storage byte length. Both buffers use the SAME module+96 heap.
```text
c0146ce4 LDW *A4[5],A0
c0146cf0 CALLP c01510e8     ; free old pointer B4=A0
c0146cf8 SHL B0,4,B0       ; 16 bytes/symbol
c0146d00 ADDAD A0,0xc,A0   ; +96 bytes, NOT +48
c0146d04 CALLP c015f644
c0146d14 STW A0,*A4[5]
c0146d18 STW B0,*A4[6]
c0146d44 CALLP c01510e8     ; free old module[7]
c0146d58 SUB B0,B1,B0
c0146d5a STW B0,*A4[8]
c0146d68 CALLP c015f644
c0146d70 STW A0,*A4[7]
```
**Confirmed:** c01510e8 frees: c01510f6 subtracts 8 from the pointer to reach its header; c0151128..1174 inserts it in address order and coalesces adjacent blocks. c015f644 calls c0151190 with A6=0; c01511c0..c8 clamps alignment to at least 8, c01511ca..d8 rounds byte counts. c0169fc0 is memcpy, NOT an allocator: c0169fcc LDB *B4++[1],A3; c016a010 STB A3,*A5++[1], plus word/doubleword copies; A4=dest, B4=source, A6=byte count. The actual entry callbacks and separate instance buffer pointers are documented here and in section 4.

## 4. Audio buffers
**Confirmed:** distinguish A4=effect instance from B4=shared service/audio ctx. c01502cc returns shared ctx=11f03b48. Its word[1] points to **11f037b0, L1D RAM**, not L2 or SDRAM:
```text
c014ff58/c014ff64 -> A4=11f03b48
c014ff70/c014ff74 -> A0=11f037b0
c014ff78 ADD A4,4,A4
c014ff7a STW A0,*A4[0]       ; service ctx[1]
```
c0165cf0..5d04 clears 128 bytes at 11f037b0; c016d188..1b0 addresses that base and its +64-byte channel. This is two 16-float channels. Stock NYC wrapper .text+ab0 copies incoming service B4 to A8, and SUB_Fx_DRV_NycMuff at .text+1b0 loads *A8[1] into B27, independently proving the audio-pointer use. Shared ctx[0]=11f03970 and ctx[2]=11f03830 are separately initialized at c014ff60..ff8a.

**Confirmed:** the effect instance is a different 20-byte object: c014ff44 returns 11f03ad0+20*slot. Its word[1] is a coefficient buffer and word[2] a state buffer, both L1D. c014fea0 initializes them:
```text
c014fee6 LDW *A6++[1],A1     ; c0183990 state-base table
c014fee8 LDW *B5++[1],B2     ; c0183978 coefficient-base table
c014ff00 STW B2,*A4[1]
c014ff08 ADDK 20,A4
c014ff0a STW A1,*A4[2]      ; software-pipelined record loop
```

| Slot | instance[1]: coefficients (840 bytes) | instance[2]: state (672 bytes) |
|---|---|---|
| 0 | 11f00000 | 11f013b0 |
| 1 | 11f00348 | 11f01650 |
| 2 | 11f00690 | 11f018f0 |
| 3 | 11f009d8 | 11f01b90 |
| 4 | 11f00d20 | 11f01e30 |

Sizes are established by c0165e98's five-slot clearing loop: c0165ea0/a4 form 0x348 and 0x2a0; c0165ee4/f0 call memset. These are fixed allocations, not entry-field requests. NYC init at .text+f92 loads instance[1] and at fb0 copies 568 bytes of .const defaults there; fca/fd0 and fe4/fe8 zero instance[2] (4+388 bytes). Its process wrapper at aa4 loads instance[2], at aae instance[1], and forwards the original instance in B6. Effect-owned state in these framework buffers is on-chip even though ELF loadable data is SDRAM. Instance[3] points to the large SDRAM work-buffer descriptor documented in section 2.

## 5. Cacheability
**Confirmed (static startup configuration):** MAR192 is written 1; MAR193..223 are written 0. Therefore 0xc0000000..0xc0ffffff is cacheable under this configuration. No exhaustive audit of later writes or runtime verification.
```text
c0159f8c/c0159f94 -> A3=0xc017be74
c0159f98 LDW *A3[0],A16
c0159fa0 MVKH 0xc0000000,A18 ; initial address
c0159fa4 MVK 0x20,B1        ; 32 MARs
c0159fa8 B c016c420
c0159fb4 AND 1,A16,A6       ; register value
c0159fc4 ADD A17,A18,A18    ; A17=0x01000000
c0159fc6 SHRU A16,1,A16
c016c424 SHRU A4,24,A8
c016c434/c438 -> A5=0x01848000
c016c448 ADDAW A5,A3,A7     ; A3=start >>24
c016c454 STW A6,*A7++[1]
```
AIS data c017be74 = 0x00000001 at res1 offset 0x6fdfc (build/codex3/words.ps1). MAR192 register = 0x01848300. Cache split from the brief is accepted context, not re-proven here. EDMA absence claim in recon/13 is rejected per brief; no EDMA ownership conclusion is made.

## 6. Levers

1. **Evidence-based, no firmware change:** use the effect's own instance[1] and instance[2] for small hot tables/state, filling them at init. NYC already copies constants into instance[1]. Budget coefficients, state, scratch and table together within the separate 840-byte/672-byte capacities; use pointers relative to the provided instance rather than hard-coded slot addresses. An 8 KiB table cannot fit in these buffers, even combined.
2. **Evidence-based rejection:** entry[5]..[8] install callbacks. An entry[5]=8192 allocation trick is invalid. Renaming .const or setting ordinary ELF section flags does not redirect the traced PT_LOAD allocations. A separate loadable segment alone still receives memory from the same SDRAM heap.
3. **Speculative optimization, no firmware change:** shrink the lookup representation or stage only a small working subset into the existing L1D buffers. Whether this saves cycles and sounds identical requires offline numerical/audio comparison and later owner-run measurement. The map proves available storage, not a performance gain. Full 8 KiB residency in L2 without a firmware change remains unproven; no exported fast-memory allocation service has been established.
4. **Evidence-based patch points; speculative implementation:** for whole-image movement, change the destination base/size tables c01839a8/c01839c0 (compressed C initialization), or the descriptor construction before c01560f0. Reserve unused L2 RAM first; 40 KiB per slot cannot simply be multiplied across five slots inside 128 KiB L2 RAM, which already holds firmware code/data. Preserve module bookkeeping, alignment and cache maintenance. No suitable unused L2 range has been established.
5. **Evidence-based patch point; speculative implementation:** for selective code/table placement, change the c01242bc -> c015f72c allocation path to choose a reserved fast heap for selected PT_LOAD segments, and make deallocation track that heap. Put the hot table in its own loadable segment if segment-level selection is desired. The existing relocation path already fixes ABS32/L16/H16 to allocated addresses, but other relocation types/range constraints and cache operations need review before implementing a mixed-region loader.

**Interpretation:** the placement suspicion is partly right: ordinary effect .text/.const reside in cacheable SDRAM, while framework coefficient/state and audio buffers reside in L1D. This does not establish that SDRAM traffic accounts for the measured 24k versus 15-17k cycle gap; cache hits, conflicts and the static timing assumptions are not measured here.

**Remaining open questions:** exact runtime segment addresses within each heap; exhaustive HeapBuf/dynamically created heap inventory and original SYS/BIOS instance names; purpose of the alternate c00d2800 image-loader region; any later MAR changes; a demonstrably free L2 reservation; and actual cache-miss contribution to CF RAT timing. NYC has empty .bss, so a nonempty stock .bss specimen has not independently exercised the proven PT_LOAD zero-fill path.

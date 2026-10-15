# Brief (Antigravity / Gemini): how many tasks run the USB event loop c0138310?

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly, including its Token economy section.
- Report: **`docs/helpers/GEMINI_TASK_INSTANCES_REPORT.md`**. Create it first with
  the headings below and commit it. After every finding, commit THAT FILE ONLY.
- Scratch folder: `build/gemini_tasks/`. This is static analysis only. Never touch
  the pedal, devices or any .exe, and never push. Do not edit any other file.
- Input: `build/fw/map/main.dis`, plus names from `recon/map/chunk_*.md` and
  `recon/map/00_library_kernel.md` (grep only).

## Background
`c0138310` is the entry function of the USB event-service task. It loops on a
mailbox receive (`c014a214` at `c0138318`) and dispatches commands. The
controller firmware calls a stock task-create wrapper `c014a400`
(`TASK_CREATE` in `firmware/controller/controller.c`). The kernel's own
task-create routine may be different.

## Tasks (one report section each)
1. **Every reference to `0xc0138310`.** Find MVK `0x8310` or `0xffff8310` paired
   with MVKH `0xc0130000` within ~16 lines, plus `.word 0xc0138310`. Use a
   Python scan. For each hit, give the address and the enclosing function.
2. **Task creation.** For each reference, show how the value is used: passed
   to a task-create routine (which one), or stored in a task descriptor table.
   Give the arguments where visible (priority, stack size, name pointer).
3. **Instance count.** Is the creating code reachable more than once, for
   example in a loop, on USB re-init, or on reconnect? Is there a guard (handle
   already non-zero)? Report the count of distinct creation sites and whether
   each can run more than once. Write "unknown" where the code does not show it.
4. **Mailbox.** Which mailbox handle does `c0138318` receive from (a B14 slot or
   a fixed address)? Does any other task receive from the same handle?

Every claim needs an address, an excerpt of at most 8 lines, and a confidence
(confirmed / likely / guess). Do not fill gaps with plausible guesses.

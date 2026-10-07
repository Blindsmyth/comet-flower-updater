# Save protocol for helper runs (owner's rule, 2026-10-07)

Usage caps and memory limits can end a run at any moment. So:

1. Create your report file FIRST, with the section headings of your brief.
2. After EVERY finding (an address identified, a routine understood, a
   question answered or ruled out), append it to the report and commit
   THAT FILE ONLY:
       git add <your report file>
       git commit -m "<report name>: <one-line finding>" -m "Co-Authored-By: <your model name>"
   Never `git add -A`, never `git add .`, never commit other files, never
   push. If git says another process holds `.git/index.lock`, wait 10 s and
   retry (another helper may be committing at the same moment).
3. Each finding states its evidence (instruction addresses and a short
   disassembly excerpt) and a confidence: confirmed / likely / guess.
4. Scratch files go only in your scratch folder, never in the repository root.

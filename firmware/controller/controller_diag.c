/* USB abort teardown DIAGNOSTIC (offline candidate only; never part of the
   lifecycle candidate, never packaged by tools/make_fs_restore_updater.py).

   Purpose: record what the stock endpoint-abort drain loop pops and recycles
   at c0120744 (see docs/helpers/USB_TEARDOWN_PATCH_SITES_2026-10-14.md). This
   OBSERVES the ownership gap; it does not fix it. A set fault bit proves the
   gap happened on that run; a clear one proves nothing about unexecuted paths.

   Context: task (abort routine), not the Hwi. No kernel calls, no printing.
   Entries are written fully BEFORE the head index is published. */
typedef unsigned int u32;

#define DESC_BASE 0xc87b9000u
#define DESC_SIZE 32u
#define DIAG_ENTRIES 24u

/* fault bits (sticky) */
#define FAULT_TYPE19_RECYCLED 0x1u   /* word0[31:27]==19 popped by abort drain */
#define FAULT_CHANNEL_MISMATCH 0x2u  /* word0[5:0] != slot-1; mapping verified for slot 4 only */
#define FAULT_RING_WRAPPED 0x4u      /* oldest entries overwritten */

typedef struct {
    u32 tag;     /* seq[15:0] | slot[23:16] | site[31:24] (1 = c0120744 pop-recycle) */
    u32 idx;     /* descriptor index from the pop */
    u32 word0;   /* descriptor word 0 as read before the recycle */
    u32 tscl;    /* TSCL low word (valid only if the timestamp counter runs) */
} DiagEntry;

typedef struct {
    u32 magic;   /* 'TDG1' once initialised */
    u32 head;    /* total entries written; slot = head % DIAG_ENTRIES */
    u32 fault;   /* sticky OR of FAULT_* */
    u32 teardown_seen;  /* count of type-19 descriptors seen */
    DiagEntry e[DIAG_ENTRIES];
} Diag;

#pragma DATA_SECTION(ctl_diag, ".ctl_state")
volatile Diag ctl_diag = { 0x54444731u, 0, 0, 0 };

/* TSCL is a control register; declared as one in c6x.h (TI CGT). */
extern cregister volatile unsigned int TSCL;

/* Called from the asm thunk with the registers saved. idx and slot come from
   the stock registers A4 (pop result) and A10 (endpoint slot). */
void controller_diag_teardown(u32 idx, u32 slot)
{
    volatile u32 *d = (volatile u32 *)(DESC_BASE + DESC_SIZE * idx);
    u32 w0 = d[0];
    u32 n = ctl_diag.head;
    volatile DiagEntry *e = &ctl_diag.e[n % DIAG_ENTRIES];
    u32 f = 0;

    if ((w0 >> 27) == 19u) {
        ctl_diag.teardown_seen++;
        f |= FAULT_TYPE19_RECYCLED;
        if ((w0 & 0x3fu) != ((slot - 1u) & 0x3fu))
            f |= FAULT_CHANNEL_MISMATCH;
    }
    if (n >= DIAG_ENTRIES)
        f |= FAULT_RING_WRAPPED;

    e->idx = idx;
    e->word0 = w0;
    e->tscl = TSCL;
    e->tag = (1u << 24) | ((slot & 0xffu) << 16) | (n & 0xffffu);
    ctl_diag.fault |= f;
    ctl_diag.head = n + 1u;   /* publish last */
}

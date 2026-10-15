/* USB abort teardown DIAGNOSTIC (offline candidate only; never part of the
   lifecycle candidate, never packaged by tools/make_fs_restore_updater.py).

   Purpose: record what the stock USB descriptor-queue code pops and recycles
   at two sites (see docs/helpers/USB_TEARDOWN_PATCH_SITES_2026-10-14.md):
     site 1  c0120744  abort drain loop (queue 25), recycles every popped entry
     site 2  c0121a18  queue 32..35 consumer c01219f4(.., B4=queue), recycles
                       every popped entry whose type != 16 (at c0121a24)
   This OBSERVES the ownership gap; it does not fix it. A set fault bit proves
   the gap happened on that run; a clear one proves nothing about unexecuted
   paths.

   Context: site 1 is the abort routine (task). The execution context of
   site 2 (task vs Hwi) is NOT proved, so every ring update runs with
   interrupts disabled (a few tens of cycles; single core). No kernel calls,
   no printing. Entries are written fully BEFORE the head index is published. */
typedef unsigned int u32;

#define DESC_BASE 0xc87b9000u
#define DESC_SIZE 32u
#define DIAG_ENTRIES 24u

/* fault bits (sticky) */
#define FAULT_TYPE19_RECYCLED 0x1u   /* site 1: word0[31:27]==19 popped by abort drain */
#define FAULT_CHANNEL_MISMATCH 0x2u  /* site 1: word0[5:0] != slot-1; mapping verified for slot 4 only */
#define FAULT_RING_WRAPPED 0x4u      /* oldest entries overwritten */
#define FAULT_TYPE19_CONSUMER 0x8u   /* site 2: word0[31:27]==19 popped by the queue 32..35 consumer
                                        (stock then recycles it at c0121a24) */

#define SITE_ABORT_DRAIN 1u
#define SITE_QUEUE_CONSUMER 2u

typedef struct {
    u32 tag;     /* seq[15:0] | aux[23:16] | site[31:24]; aux = slot (site 1) or queue (site 2) */
    u32 idx;     /* descriptor index from the pop */
    u32 word0;   /* descriptor word 0 as read before the recycle */
    u32 tscl;    /* TSCL low word (valid only if the timestamp counter runs) */
} DiagEntry;

typedef struct {
    u32 magic;   /* 'TDG1' once initialised */
    u32 head;    /* total entries written; slot = head % DIAG_ENTRIES */
    u32 fault;   /* sticky OR of FAULT_* */
    u32 teardown_seen;  /* count of type-19 descriptors seen (both sites) */
    u32 consumer_pops;  /* site 2: all pops by the queue 32..35 consumer (type 16 included) */
    u32 consumer_other; /* site 2: pops with type != 16 (logged in the ring) */
    DiagEntry e[DIAG_ENTRIES];
} Diag;

#pragma DATA_SECTION(ctl_diag, ".ctl_state")
volatile Diag ctl_diag = { 0x54444731u, 0, 0, 0, 0, 0 };

/* TSCL is a control register; declared as one in c6x.h (TI CGT). */
extern cregister volatile unsigned int TSCL;

/* Append one entry. Caller holds interrupts disabled. */
static void diag_log(u32 site, u32 aux, u32 idx, u32 w0, u32 f)
{
    u32 n = ctl_diag.head;
    volatile DiagEntry *e = &ctl_diag.e[n % DIAG_ENTRIES];

    if (n >= DIAG_ENTRIES)
        f |= FAULT_RING_WRAPPED;
    e->idx = idx;
    e->word0 = w0;
    e->tscl = TSCL;
    e->tag = (site << 24) | ((aux & 0xffu) << 16) | (n & 0xffffu);
    ctl_diag.fault |= f;
    ctl_diag.head = n + 1u;   /* publish last */
}

/* Site 1. Called from the asm thunk with the registers saved. idx and slot
   come from the stock registers A4 (pop result) and A10 (endpoint slot). */
void controller_diag_teardown(u32 idx, u32 slot)
{
    volatile u32 *d = (volatile u32 *)(DESC_BASE + DESC_SIZE * idx);
    u32 w0 = d[0];
    u32 f = 0;
    u32 csr = _disable_interrupts();

    if ((w0 >> 27) == 19u) {
        ctl_diag.teardown_seen++;
        f |= FAULT_TYPE19_RECYCLED;
        if ((w0 & 0x3fu) != ((slot - 1u) & 0x3fu))
            f |= FAULT_CHANNEL_MISMATCH;
    }
    diag_log(SITE_ABORT_DRAIN, slot, idx, w0, f);
    _restore_interrupts(csr);
}

/* Site 2. Called from the asm thunk at c0121a18 (stock: CALLP c011fa54, the
   type==16 test) with A4 = popped descriptor index and B4 = queue number
   (32..35; callers set B4 with MVK at c0121e82/e94/c012218c/c012219a).
   Stock then recycles every entry with type != 16 (c0121a24), so only those
   are logged; type-16 pops are counted. */
void controller_diag_consumer(u32 idx, u32 queue)
{
    volatile u32 *d = (volatile u32 *)(DESC_BASE + DESC_SIZE * idx);
    u32 w0 = d[0];
    u32 csr = _disable_interrupts();

    ctl_diag.consumer_pops++;
    if ((w0 >> 27) != 16u) {
        u32 f = 0;
        ctl_diag.consumer_other++;
        if ((w0 >> 27) == 19u) {
            ctl_diag.teardown_seen++;
            f |= FAULT_TYPE19_CONSUMER;
        }
        diag_log(SITE_QUEUE_CONSUMER, queue, idx, w0, f);
    }
    _restore_interrupts(csr);
}

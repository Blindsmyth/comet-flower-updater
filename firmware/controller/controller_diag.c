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

/* ---- Readback (diag build only) -------------------------------------------
   The ring is useless unless it leaves the device. On the combined footswitch
   gesture (event 4) the MIDI worker snapshots ctl_diag plus TX record fields,
   then streams the snapshot as Control Change messages on channel 1 through
   the same ring/append path as ordinary controller output:
     CC119=127                        begin
     CC102..106 = word bits 0-6, 7-13, 14-20, 21-27, 28-31   (one word = 5 CCs)
     CC119=1                          end
   Words: DUMP_MAGIC, word count, Diag (102 words), then for TX slots 1..4 the
   record (0xc011297c + 0x2a8*N) fields [2],[3],[5],[9], then the MIDI worker
   stack: size (task word 7), base (task word 8), the count of untouched
   0xbe fill bytes up from the base (high-water mark; c016e300 is the stock
   check of the base byte against 0xbe; c0152878..2910 stores size/base), and
   the number of workers created this boot. Every Task_create fills the whole
   new stack with 0xbe (c015f820 -> c016b140, gated by the halfword at
   c0181ac4), and each new transport creates a new worker, so the mark covers
   only the current worker instance, not earlier connections. The
   scan runs only if size == 0x800 (the worker descriptor's request) and the
   base lies in DDR; otherwise the count is 0xffffffff. Field [5] stuck
   nonzero after a reconnect is the liveness signature from
   docs/helpers/SOL_EXPIRY_RECOVERY_REPORT.md (Claude review).
   peek/commit run only in the MIDI worker under MIDI_LOCK; request runs in
   MainApp and only increments a word. */
#define DUMP_MAGIC 0x31504d44u                 /* 'DMP1' */
#define DIAG_WORDS (sizeof(Diag) / 4u)
#define TXREC(n) ((volatile u32 *)(0xc011297cu + 0x2a8u * (n)))
#define DUMP_WORDS (2u + DIAG_WORDS + 16u + 4u)
#define DUMP_CCS (5u * DUMP_WORDS + 2u)

#pragma DATA_SECTION(diag_dump, ".ctl_state")
struct {
    volatile u32 req;   /* MainApp increments */
    u32 seen;           /* worker: last req snapshotted */
    u32 pos;            /* next CC index; DUMP_CCS when idle */
    u32 worker;         /* task handle returned by the worker create */
    u32 creates;        /* worker creations this boot (the mark resets on each) */
    u32 w[DUMP_WORDS];
} diag_dump = { 0, 0, DUMP_CCS, 0, 0 };

void controller_diag_worker(u32 task)
{
    diag_dump.worker = task;
    diag_dump.creates++;
}

static void diag_stack(u32 *size, u32 *base, u32 *unused)
{
    volatile u32 *t = (volatile u32 *)diag_dump.worker;
    volatile unsigned char *p;
    u32 n = 0;
    *size = *base = 0;
    *unused = 0xffffffffu;
    if (diag_dump.worker < 0xc0000000u || diag_dump.worker >= 0xd0000000u)
        return;
    *size = t[7];
    *base = t[8];
    if (*size != 0x800u || *base < 0xc0000000u || *base >= 0xd0000000u - 0x800u)
        return;
    p = (volatile unsigned char *)*base;
    while (n < *size && p[n] == 0xbeu)
        n++;
    *unused = n;
}

void controller_diag_request(void)
{
    diag_dump.req++;
}

static void diag_snapshot(void)
{
    u32 i, k = 0, n;
    u32 csr = _disable_interrupts();
    diag_dump.w[k++] = DUMP_MAGIC;
    diag_dump.w[k++] = DUMP_WORDS - 2u;
    for (i = 0; i < DIAG_WORDS; i++)
        diag_dump.w[k++] = ((volatile u32 *)&ctl_diag)[i];
    for (n = 1; n <= 4u; n++) {
        diag_dump.w[k++] = TXREC(n)[2];
        diag_dump.w[k++] = TXREC(n)[3];
        diag_dump.w[k++] = TXREC(n)[5];
        diag_dump.w[k++] = TXREC(n)[9];
    }
    _restore_interrupts(csr);
    diag_stack(&diag_dump.w[k], &diag_dump.w[k + 1], &diag_dump.w[k + 2]);
    diag_dump.w[k + 3] = diag_dump.creates;
}

/* Next CC to send, if any. A new request restarts from a fresh snapshot. */
int controller_diag_peek(u32 *control, u32 *value)
{
    u32 p, part;
    if (diag_dump.req != diag_dump.seen) {
        diag_dump.seen = diag_dump.req;
        diag_snapshot();
        diag_dump.pos = 0;
    }
    p = diag_dump.pos;
    if (p >= DUMP_CCS)
        return 0;
    if (p == 0 || p == DUMP_CCS - 1u) {
        *control = 119u;
        *value = p == 0 ? 127u : 1u;
        return 1;
    }
    part = (p - 1u) % 5u;
    *control = 102u + part;
    *value = (diag_dump.w[(p - 1u) / 5u] >> (7u * part)) & 0x7fu;
    return 1;
}

void controller_diag_commit(void)
{
    if (diag_dump.pos < DUMP_CCS)
        diag_dump.pos++;
}

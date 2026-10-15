"""Generate effects/common/hiwatt_netgen.h: the three DR103 linear networks
(effects/common/hiwatt_nets.h) derived as straight-line C, no loops, no
pivoting, no structural zeros, replacing the per-block mna_derive and the
101-position V1 / back-half tables.

Why: the generic mna_derive (pivoting, short variable-bound loops) cost ~25k
cycles per block on the pedal for the tone stack alone (recon/04, DR103D
derivation slot), and the two knob tables (20.6 KB) put DR103 10.5 KB over the
40 KiB slot heap. The topologies are fixed, so the elimination is traced here
once and emitted as plain arithmetic the C6x compiler schedules freely.

  hw_stack_derive  tone stack + master. The master pot (E-OUT-gnd) only loads
                   node D with a fixed 22k + Rhi + Rlo leg: folded, the output
                   is vD * Rlo / (22k + Rhi + Rlo). 8 nodes, 5 caps.
  hw_v1_derive     V1 plate network + Volume. 5 nodes, 2 caps.
  hw_bh_derive     back half + Presence (controlled sources, 11 nodes, 5 caps,
                   2 inputs). Presence only changes two branches (P1-W, W-P2),
                   so G = G0 + U diag(dg) U^T; the Woodbury identity reduces
                   the derivation to a 2x2 solve and a rank-2 correction of
                   constants computed here in double (numpy).

Stack and V1 are grounded Laplacians (resistors only): their elimination runs
in GTH form (Grassmann-Taksar-Heyman), positive sums only, so a 20-ohm wiper
floor (50,000 uS beside ~5 uS) cannot cancel; plain Gauss lost 0.21 dB there.

Common tail (units as mna_ss.h: uS, uA, nF, V):
  G [Zx | Zu] = [E | B],  S = E^T Zx,  T = E^T Zu,  wz = w^T [Zx | Zu]
  M = S + hD,  D = diag(1e3 / C)
  dA = -2h D M^-1,  dB = h D M^-1 T,  cy = wz_x S^-1,  dy = wz_u - cy T
equal to mna_derive's (I - hA)[dA | dB] = [2hA | hB], A = -D S^-1,
B = D S^-1 T, since (I - hA)^-1 = S (S + hD)^-1 (no symmetry assumed).

    python tools/gen_hw_nets.py     # rewrites effects/common/hiwatt_netgen.h
Host check: tests/host/build_hiwatt_netgen_test.bat.
"""
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "effects" / "common" / "hiwatt_netgen.h"


class Emit:
    """Straight-line code builder; None stands for a structural zero."""

    def __init__(self):
        self.lines, self.n = [], 0

    def tmp(self, expr):
        name = f"t{self.n}"
        self.n += 1
        self.lines.append(f"    float {name} = {expr};")
        return name

    def note(self, text):
        self.lines.append(f"    /* {text} */")

    def mul(self, a, b):
        if a is None or b is None:
            return None
        if a == "1.0f":
            return b
        if b == "1.0f":
            return a
        if a == "-1.0f":
            return self.tmp(f"-{b}")
        if b == "-1.0f":
            return self.tmp(f"-{a}")
        return self.tmp(f"{a} * {b}")

    def add(self, a, b):
        if a is None:
            return b
        if b is None:
            return a
        return self.tmp(f"{a} + {b}")

    def sub(self, a, b):
        if b is None:
            return a
        if a is None:
            return self.tmp(f"-{b}")
        return self.tmp(f"{a} - {b}")

    def solve(self, Mx, rhs_cols):
        """Gauss without pivoting on a dense k x k (copied); returns the
        solution of each rhs column. Callers guarantee no pivot is needed."""
        Mx = [row[:] for row in Mx]
        rhs = [col[:] for col in rhs_cols]
        n = len(Mx)
        iv = [None] * n
        for k in range(n):
            iv[k] = self.tmp(f"mna_rcp({Mx[k][k]})")
            for i in range(k + 1, n):
                f = self.mul(Mx[i][k], iv[k])
                for j in range(k + 1, n):
                    Mx[i][j] = self.sub(Mx[i][j], self.mul(f, Mx[k][j]))
                for col in rhs:
                    if col[k] is not None:
                        col[i] = self.sub(col[i], self.mul(f, col[k]))
        out = []
        for col in rhs:
            x = [None] * n
            for k in range(n - 1, -1, -1):
                acc = col[k]
                for i in range(k + 1, n):
                    if x[i] is not None:
                        acc = self.sub(acc, self.mul(Mx[k][i], x[i]))
                x[k] = self.mul(acc, iv[k]) if acc is not None else None
            out.append(x)
        return out


def lit(v):
    return f"{v:.9e}f"


def tail(e, S, T, wz, cap_nf, symmetric):
    """The common tail: S (k x k), T (k lists, one per input), wz (k + nu)
    -> packed [dA k*k][dB k*nu][cy k][dy nu] written to out[]."""
    k, nu = len(S), len(T[0])
    if symmetric:                       # exact symmetry: use the upper half
        for r in range(k):
            for c in range(r):
                S[r][c] = S[c][r]
    e.note("cy = wz_x S^-1 (S^T cy^T = wz_x^T), dy = wz_u - cy T")
    St = [[S[c][r] for c in range(k)] for r in range(k)]
    cy = e.solve(St, [wz[:k]])[0]
    dy = []
    for u in range(nu):
        acc = wz[k + u]
        for r in range(k):
            acc = e.sub(acc, e.mul(cy[r], T[r][u]))
        dy.append(acc)
    e.note("M = S + hD; dA = -2h D M^-1, dB = h D M^-1 T")
    hd = [e.tmp(f"h * {lit(1.0e3 / c)}") for c in cap_nf]
    Mm = [[S[r][c] if r != c else e.tmp(f"{S[r][c]} + {hd[r]}") for c in range(k)] for r in range(k)]
    ident = [["1.0f" if r == c else None for r in range(k)] for c in range(k)]
    sol = e.solve(Mm, ident + [[T[r][u] for r in range(k)] for u in range(nu)])
    e.note(f"packed [dA {k}x{k}][dB {k}x{nu}][cy {k}][dy {nu}] (mna_ss.h layout)")
    L = e.lines
    for i in range(k):
        for j in range(k):
            v = sol[j][i]
            L.append(f"    out[{i * k + j}] = {'0.0f' if v is None else f'-2.0f * {hd[i]} * {v}'};")
    for i in range(k):
        for u in range(nu):
            v = sol[k + u][i]
            L.append(f"    out[{k * k + i * nu + u}] = {'0.0f' if v is None else f'{hd[i]} * {v}'};")
    for i in range(k):
        L.append(f"    out[{k * k + k * nu + i}] = {'0.0f' if cy[i] is None else cy[i]};")
    for u in range(nu):
        L.append(f"    out[{k * k + k * nu + k + u}] = {'0.0f' if dy[u] is None else dy[u]};")


def laplacian(e, nn, res, caps, inj, wout):
    """GTH elimination of a grounded resistor network. res: (i, j, uS expr),
    j = -1 ground; caps: (i, j, nF); inj: node -> input-current expr (one
    input); wout: node -> output weight expr. Writes the packed system."""
    nk = len(caps)
    cb = [[None] * nn for _ in range(nn)]
    g0 = [None] * nn
    for i, j, gg in res:
        if j < 0:
            g0[i] = e.add(g0[i], gg)
        else:
            cb[i][j] = e.add(cb[i][j], gg)
            cb[j][i] = cb[i][j]
    R = [[None] * (nk + 1) for _ in range(nn)]
    for c, (i, j, _) in enumerate(caps):
        R[i][c] = "1.0f"
        if j >= 0:
            R[j][c] = "-1.0f"
    for node, expr in inj.items():
        R[node][nk] = expr
    e.note("forward elimination in GTH form (no pivoting, no subtraction)")
    inv = [None] * nn
    for k in range(nn):
        piv = g0[k]
        for j in range(k + 1, nn):
            piv = e.add(piv, cb[k][j])
        inv[k] = e.tmp(f"mna_rcp({piv})")
        f = {i: e.mul(cb[i][k], inv[k]) for i in range(k + 1, nn) if cb[i][k] is not None}
        for i in f:
            for j in f:
                if i < j:
                    cb[i][j] = e.add(cb[i][j], e.mul(f[i], cb[k][j]))
                    cb[j][i] = cb[i][j]
            if g0[k] is not None:
                g0[i] = e.add(g0[i], e.mul(f[i], g0[k]))
            for c in range(nk + 1):
                if R[k][c] is not None:
                    R[i][c] = e.add(R[i][c], e.mul(f[i], R[k][c]))
    e.note("back substitution: Z = [Zx | Zu]")
    Z = [[None] * (nk + 1) for _ in range(nn)]
    for k in range(nn - 1, -1, -1):
        for c in range(nk + 1):
            acc = R[k][c]
            for i in range(k + 1, nn):
                if cb[k][i] is not None and Z[i][c] is not None:
                    acc = e.add(acc, e.mul(cb[k][i], Z[i][c]))
            Z[k][c] = e.mul(acc, inv[k]) if acc is not None else None

    def zd(i, j, c):
        return e.sub(Z[i][c] if i >= 0 else None, Z[j][c] if j >= 0 else None)

    e.note("S = E^T Zx, T = E^T Zu, wz = w^T Z")
    S = [[zd(caps[r][0], caps[r][1], c) for c in range(nk)] for r in range(nk)]
    T = [[zd(caps[r][0], caps[r][1], nk)] for r in range(nk)]
    wz = []
    for c in range(nk + 1):
        acc = None
        for node, w in wout.items():
            acc = e.add(acc, e.mul(w, Z[node][c]))
        wz.append(acc)
    tail(e, S, T, wz, [c for _, _, c in caps], symmetric=True)


def gen_stack():
    e = Emit()
    IN, A, B_, D, CN, F, GN, K = range(8)
    e.lines += [
        "    /* pot resistances, ohms (hw_stack: 20-ohm wiper floor) */",
        "    float lo = hw_atap(mv), ab = hw_atap(b);",
        "    float rtb = hw_maxf((1.0f - t) * 220e3f, HW_RWIPR), rtc = hw_maxf(t * 220e3f, HW_RWIPR);",
        "    float rmh = hw_maxf((1.0f - lo) * 220e3f, HW_RWIPR), rml = hw_maxf(lo * 220e3f, HW_RWIPR);",
        "    float rmid = hw_maxf(mid * 100e3f, HW_RWIPR), rbas = hw_maxf(ab * 470e3f, HW_RWIPR);",
        "    float rleg = 22e3f + rmh + rml;",
    ]
    gtb = e.tmp("1.0e6f * mna_rcp(rtb)")
    gtc = e.tmp("1.0e6f * mna_rcp(rtc)")
    gleg = e.tmp("1.0e6f * mna_rcp(rleg)")
    gmid = e.tmp("1.0e6f * mna_rcp(rmid)")
    gbas = e.tmp("1.0e6f * mna_rcp(rbas)")
    gout = e.tmp("rml * mna_rcp(rleg)")
    gsrc = "(1.0e6f / (HW_RA3 + (HW_MU3 + 1.0f) * 2.2e3f))"
    res = [(IN, -1, gsrc), (IN, -1, "(1.0e6f / 220e3f)"), (A, CN, "(1.0e6f / 220e3f)"),
           (B_, D, gtb), (D, CN, gtc), (D, -1, gleg), (CN, F, "(1.0e6f / 22e3f)"),
           (F, GN, gmid), (GN, -1, gbas), (IN, K, "(1.0e6f / 100e3f)")]
    caps = [(IN, A, 1.0), (A, B_, 0.22), (F, GN, 1.0), (K, GN, 47.0), (K, -1, 47.0)]
    laplacian(e, 8, res, caps, {IN: gsrc}, {D: gout})
    return e


def gen_v1():
    e = Emit()
    P, T_, W, G2, M = range(5)
    e.lines += [
        "    /* Volume (470k-A): hw_v1net, 20-ohm wiper floor */",
        "    float a = hw_atap(vol01);",
    ]
    ghi = e.tmp("1.0e6f * mna_rcp(hw_maxf((1.0f - a) * 470e3f, HW_RWIPR))")
    glo = e.tmp("1.0e6f * mna_rcp(hw_maxf(a * 470e3f, HW_RWIPR))")
    gra = "(1.0e6f / HW_RA3)"
    res = [(M, -1, gra), (M, P, "(1.0e6f / ((HW_MU3 + 1.0f) * 2.2e3f))"),
           (P, -1, "(1.0e6f / 220e3f)"), (T_, W, ghi), (W, -1, glo),
           (W, G2, "(1.0e6f / 470e3f)"), (G2, -1, "(1.0e6f / 470e3f)")]
    caps = [(M, P, 47.0 / 101.0), (P, T_, 22.0)]
    laplacian(e, 5, res, caps, {M: gra}, {G2: "1.0f"})
    return e


# ---- back half: numpy model of hw_backhalf (MNA in uS / nF, as mna_ss.h) ----
MU3, RA3, MU4, RA4 = 100.0, 62.5e3, 60.0, 10.9e3
GM3 = MU3 / RA3
KTAPLIN = -56.57 * 48.5 / (2.0 * 38.0)
KLOOP = -KTAPLIN
K3, P3, GB3, KB3, P1, W, P2, N, X, M, KT = range(11)
BH_CAPS = [(K3, -1, 47.0), (P3, GB3, 22.0), (P3, P1, 1.0), (P2, N, 47.0), (X, -1, 10.0)]


def bh_matrices(ga, gb):
    """G (11x11, uS), B (11x2), with the presence branches P1-W = ga and
    W-P2 = gb (uS); mirrors hiwatt_nets.h hw_backhalf."""
    G = np.zeros((11, 11))
    B = np.zeros((11, 2))

    def r(i, j, ohms):
        g = 1e6 / ohms
        G[i, i] += g
        if j >= 0:
            G[j, j] += g
            G[i, j] -= g
            G[j, i] -= g

    def gg(row, col, s):
        G[row, col] += s * 1e6

    gra = 1.0 / RA3
    B[P3, 0] += -GM3 * 1e6
    B[K3, 0] += GM3 * 1e6
    gg(P3, K3, -GM3); gg(P3, K3, -gra); gg(P3, P3, gra)
    gg(K3, K3, GM3); gg(K3, P3, -gra); gg(K3, K3, gra)
    r(K3, -1, 2.2e3); r(P3, -1, 100e3)
    r(P3, GB3, 1.8e6); r(GB3, -1, 1.0e6)
    gg(KB3, GB3, -GM3); gg(KB3, KB3, GM3 + gra); r(KB3, -1, 100e3)
    for i, j, g in ((P1, W, ga), (W, P2, gb)):
        G[i, i] += g; G[j, j] += g; G[i, j] -= g; G[j, i] -= g
    r(W, -1, 100.0)
    r(N, -1, 10e3); B[N, 1] += 1e6 / 10e3
    r(N, X, 470.0); r(N, M, 2.2e3); r(M, KT, 22e3); r(KB3, KT, 1.0e6)
    gg(KT, KT, (MU4 + 1.0) / (RA4 + 82e3)); gg(KT, KB3, -MU4 / (RA4 + 82e3))
    gg(KT, KT, (MU4 + 1.0) / (RA4 + 91e3)); gg(KT, M, -MU4 / (RA4 + 91e3))
    gg(N, KB3, -KLOOP / 10e3); gg(N, M, KLOOP / 10e3)
    return G, B


def bh_E():
    E = np.zeros((11, 5))
    for c, (i, j, _) in enumerate(BH_CAPS):
        E[i, c] = 1.0
        if j >= 0:
            E[j, c] = -1.0
    return E


BH_W = np.zeros(11)
BH_W[KB3], BH_W[M] = 1.0, -1.0
BH_G0 = 1e6 / 50e3          # reference: presence at half (both branches 50k)


def gen_bh():
    G0, B = bh_matrices(BH_G0, BH_G0)
    E = bh_E()
    U = np.zeros((11, 2))
    U[P1, 0], U[W, 0] = 1.0, -1.0          # branch a: P1 - W
    U[W, 1], U[P2, 1] = 1.0, -1.0          # branch b: W - P2
    RHS = np.hstack([E, B])                # 11 x 7
    Z0 = np.linalg.solve(G0, RHS)
    W0 = np.linalg.solve(G0, U)
    K = U.T @ W0                           # 2 x 2
    Y0 = U.T @ Z0                          # 2 x 7
    SZ0 = E.T @ Z0                         # 5 x 7: [S0 | T0]
    EW0 = E.T @ W0                         # 5 x 2
    wZ0 = BH_W @ Z0                        # 7
    wW0 = BH_W @ W0                        # 2
    detK = np.linalg.det(K)
    e = Emit()
    e.lines += [
        "    /* Presence: P1-W = x 100k, W-P2 = (1-x) 100k (1-ohm floor), as hw_backhalf;",
        "     * G = G0 + U diag(d) U^T with G0 at x = 0.5 (constants from tools/gen_hw_nets.py, double) */",
        "    float x = pres01 < 0.0f ? 0.0f : (pres01 > 1.0f ? 1.0f : pres01);",
    ]
    d1 = e.tmp(f"1.0e6f * mna_rcp(hw_maxf(x * 100e3f, 1.0f)) - {lit(BH_G0)}")
    d2 = e.tmp(f"1.0e6f * mna_rcp(hw_maxf((1.0f - x) * 100e3f, 1.0f)) - {lit(BH_G0)}")
    e.note("Woodbury: C = (I + diag(d) K)^-1 diag(d), det expanded in d1, d2")
    det = e.tmp(f"1.0f + {d1} * {lit(K[0, 0])} + {d2} * {lit(K[1, 1])} + {d1} * {d2} * {lit(detK)}")
    idet = e.tmp(f"mna_rcp({det})")
    # M2 = I + diag(d) K; C = M2^-1 diag(d)
    c00 = e.tmp(f"(1.0f + {d2} * {lit(K[1, 1])}) * {d1} * {idet}")
    c01 = e.tmp(f"-({d1} * {lit(K[0, 1])}) * {d2} * {idet}")
    c10 = e.tmp(f"-({d2} * {lit(K[1, 0])}) * {d1} * {idet}")
    c11 = e.tmp(f"(1.0f + {d1} * {lit(K[0, 0])}) * {d2} * {idet}")
    C = [[c00, c01], [c10, c11]]
    e.note("P = C Y0; [S | T] = E^T Z0 - (E^T W0) P; wz = w^T Z0 - (w^T W0) P")
    P = [[e.tmp(f"{C[i][0]} * {lit(Y0[0, c])} + {C[i][1]} * {lit(Y0[1, c])}") for c in range(7)] for i in range(2)]
    ST = [[e.tmp(f"{lit(SZ0[r, c])} - ({lit(EW0[r, 0])} * {P[0][c]} + {lit(EW0[r, 1])} * {P[1][c]})")
           for c in range(7)] for r in range(5)]
    wz = [e.tmp(f"{lit(wZ0[c])} - ({lit(wW0[0])} * {P[0][c]} + {lit(wW0[1])} * {P[1][c]})") for c in range(7)]
    S = [row[:5] for row in ST]
    T = [row[5:] for row in ST]
    tail(e, S, T, wz, [c for _, _, c in BH_CAPS], symmetric=False)
    return e


def main():
    parts = []
    for name, sig, doc, e in (
        ("hw_stack_derive", "float t, float mid, float b, float mv, float fs, float *out",
         "tone stack + master: t, mid, b, mv in 0..1 as hw_stack; out = MNA_SS_SIZE(5, 1)", gen_stack()),
        ("hw_v1_derive", "float vol01, float fs, float *out",
         "V1 network + Volume (0..1) as hw_v1net; out = MNA_SS_SIZE(2, 1)", gen_v1()),
        ("hw_bh_derive", "float pres01, float fs, float *out",
         "back half + Presence (0..1) as hw_backhalf; out = MNA_SS_SIZE(5, 2)", gen_bh()),
    ):
        parts.append(f"/* {doc} ({e.n} temporaries) */\n"
                     f"MNA_INLINE void {name}({sig})\n{{\n"
                     f"    float h = 0.5f * mna_rcp(fs);\n" + "\n".join(e.lines) + "\n}\n")
    hdr = ("/* hiwatt_netgen.h - GENERATED by tools/gen_hw_nets.py; do not edit.\n"
           " * The DR103 networks of hiwatt_nets.h derived as straight-line code (no\n"
           " * loops, pivoting or structural zeros), packed as mna_derive writes them.\n"
           " * Host check: tests/host/build_hiwatt_netgen_test.bat. */\n"
           "#ifndef HIWATT_NETGEN_H\n#define HIWATT_NETGEN_H\n\n"
           "#include \"hiwatt_nets.h\"\n\n" + "\n".join(parts) + "\n#endif /* HIWATT_NETGEN_H */\n")
    OUT.write_text(hdr, encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

"""Generate effects/common/hiwatt_stackgen.h: the DR103 tone stack + master as
straight-line C (no loops, no pivoting, no structural zeros).

Why: the generic mna_derive (10 nodes, partial pivoting, short variable-bound
loops) cost ~25k cycles per block on the pedal (recon/04, DR103D derivation
slot) and runs every block. The stack's topology is fixed, so the Gauss
elimination can be traced once here over its sparsity pattern and emitted as
plain arithmetic the C6x compiler schedules freely.

Network (effects/common/hiwatt_nets.h hw_stack, unchanged values):
  the master pot (E-OUT-gnd) only loads node D with a fixed 22k + 220k leg, so
  it is folded: D sees 1/(22k + Rhi + Rlo) to ground and the output is
  vD * Rlo / (22k + Rhi + Rlo). Eight nodes remain, five capacitors.
Formulation (same units and packed output as mna_ss.h: uS, uA, nF):
  G [Zx | Zu] = [E | B]           (G SPD: resistors only -> no pivoting)
  S = E^T Zx, T = E^T Zu, wz = w^T [Zx | Zu]
  M = S + hD,  D = diag(1e3 / C)  (S SPD -> M SPD -> no pivoting)
  dA = -2h D M^-1,  dB = h D M^-1 T
  cy^T = S^-1 wz_x^T,  dy = wz_u - cy T
which equals mna_derive's (I - hA)[dA | dB] = [2hA | hB] with A = -D S^-1,
B = D S^-1 T (algebra in the header comment).

    python tools/gen_hw_stack.py        # rewrites effects/common/hiwatt_stackgen.h
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "effects" / "common" / "hiwatt_stackgen.h"

# nodes after folding E and OUT into D
IN, A, B_, D, CN, F, GN, K = range(8)
NN = 8
NAMES = ["IN", "A", "B", "D", "Cn", "F", "Gn", "K"]


class Emit:
    def __init__(self):
        self.lines, self.n = [], 0

    def tmp(self, expr):
        name = f"t{self.n}"
        self.n += 1
        self.lines.append(f"    float {name} = {expr};")
        return name


def gen():
    e = Emit()
    L = e.lines
    L.append("    /* pot resistances, ohms (hw_stack: 20-ohm wiper floor) */")
    L.append("    float lo = hw_atap(mv), ab = hw_atap(b);")
    L.append("    float rtb = hw_maxf((1.0f - t) * 220e3f, HW_RWIPR), rtc = hw_maxf(t * 220e3f, HW_RWIPR);")
    L.append("    float rmh = hw_maxf((1.0f - lo) * 220e3f, HW_RWIPR), rml = hw_maxf(lo * 220e3f, HW_RWIPR);")
    L.append("    float rmid = hw_maxf(mid * 100e3f, HW_RWIPR), rbas = hw_maxf(ab * 470e3f, HW_RWIPR);")
    L.append("    float rleg = 22e3f + rmh + rml;")
    L.append("    /* conductances, uS */")
    g = {}
    g["src"] = "(1.0e6f / (HW_RA3 + (HW_MU3 + 1.0f) * 2.2e3f))"   # constant: folded
    g["tb"] = e.tmp("1.0e6f * mna_rcp(rtb)")
    g["tc"] = e.tmp("1.0e6f * mna_rcp(rtc)")
    g["leg"] = e.tmp("1.0e6f * mna_rcp(rleg)")
    g["mid"] = e.tmp("1.0e6f * mna_rcp(rmid)")
    g["bas"] = e.tmp("1.0e6f * mna_rcp(rbas)")
    gout = e.tmp("rml * mna_rcp(rleg)")
    # resistors: (i, j, conductance expr), j = -1 ground
    res = [
        (IN, -1, g["src"]), (IN, -1, "(1.0e6f / 220e3f)"),
        (A, CN, "(1.0e6f / 220e3f)"),
        (B_, D, g["tb"]), (D, CN, g["tc"]), (D, -1, g["leg"]),
        (CN, F, "(1.0e6f / 22e3f)"),
        (F, GN, g["mid"]), (GN, -1, g["bas"]),
        (IN, K, "(1.0e6f / 100e3f)"),
    ]
    caps = [(IN, A, 1.0), (A, B_, 0.22), (F, GN, 1.0), (K, GN, 47.0), (K, -1, 47.0)]   # nF
    NK = len(caps)
    # RHS columns: E (k caps), then B (input current per volt: gsrc at IN)
    R = [[None] * (NK + 1) for _ in range(NN)]
    for c, (i, j, _) in enumerate(caps):
        R[i][c] = "1.0f"
        if j >= 0:
            R[j][c] = "-1.0f"
    R[IN][NK] = g["src"]

    # GTH form (Grassmann-Taksar-Heyman): G is a grounded Laplacian, so keep
    # the positive branch conductances cb[i][j] = -G[i][j] and the ground
    # conductances g0[i], and rebuild each pivot as g0 + sum of branches.
    # Elimination then only adds positive numbers: a 20-ohm wiper floor
    # (50,000 uS beside ~5 uS) no longer cancels catastrophically, which
    # plain Gauss did (0.21 dB at treble 1 / bass 0).
    L.append("    /* branch and ground conductances (uS), structural nonzeros only */")
    cb = [[None] * NN for _ in range(NN)]
    g0 = [None] * NN
    for i, j, gg in res:
        if j < 0:
            g0[i] = gg if g0[i] is None else e.tmp(f"{g0[i]} + {gg}")
        else:
            cb[i][j] = gg if cb[i][j] is None else e.tmp(f"{cb[i][j]} + {gg}")
            cb[j][i] = cb[i][j]
    Rv = [[R[i][c] for c in range(NK + 1)] for i in range(NN)]

    def mul(a, b):
        if a is None or b is None:
            return None
        if a == "1.0f":
            return b
        if b == "1.0f":
            return a
        if a == "-1.0f":
            return e.tmp(f"-{b}")
        if b == "-1.0f":
            return e.tmp(f"-{a}")
        return e.tmp(f"{a} * {b}")

    def sub(a, b):          # a - b, None = 0
        if b is None:
            return a
        if a is None:
            return e.tmp(f"-{b}")
        return e.tmp(f"{a} - {b}")

    def add(a, b):
        if a is None:
            return b
        if b is None:
            return a
        return e.tmp(f"{a} + {b}")

    # elimination order: as numbered (fill is tiny for 8 nodes)
    L.append("    /* forward elimination in GTH form (no pivoting, no subtraction) */")
    inv = [None] * NN
    for k in range(NN):
        piv = g0[k]
        for j in range(k + 1, NN):
            piv = add(piv, cb[k][j])
        inv[k] = e.tmp(f"mna_rcp({piv})")
        f = {i: mul(cb[i][k], inv[k]) for i in range(k + 1, NN) if cb[i][k] is not None}
        for i in f:
            for j in f:
                if i < j:
                    cb[i][j] = add(cb[i][j], mul(f[i], cb[k][j]))
                    cb[j][i] = cb[i][j]
            if g0[k] is not None:
                g0[i] = add(g0[i], mul(f[i], g0[k]))
            for c in range(NK + 1):
                if Rv[k][c] is not None:
                    Rv[i][c] = add(Rv[i][c], mul(f[i], Rv[k][c]))
    L.append("    /* back substitution: Z = [Zx | Zu] */")
    Z = [[None] * (NK + 1) for _ in range(NN)]
    for k in range(NN - 1, -1, -1):
        for c in range(NK + 1):
            acc = Rv[k][c]
            for i in range(k + 1, NN):
                if cb[k][i] is not None and Z[i][c] is not None:
                    acc = add(acc, mul(cb[k][i], Z[i][c]))
            Z[k][c] = mul(acc, inv[k]) if acc is not None else None

    def zdiff(i, j, c):
        a = Z[i][c] if i >= 0 else None
        b = Z[j][c] if j >= 0 else None
        return sub(a, b)

    L.append("    /* S = E^T Zx (SPD), T = E^T Zu, wz = gout * Z[D] */")
    S = [[zdiff(caps[r][0], caps[r][1], c) for c in range(NK)] for r in range(NK)]
    T = [zdiff(caps[r][0], caps[r][1], NK) for r in range(NK)]
    wz = [mul(gout, Z[D][c]) for c in range(NK + 1)]
    for r in range(NK):          # symmetric in exact arithmetic: use the upper half
        for c in range(r):
            S[r][c] = S[c][r]

    def chol_solve(Mx, rhs_cols):
        """Gauss without pivoting on a dense symmetric k x k (copied), solve for
        each rhs column (lists); returns solution columns."""
        Mx = [row[:] for row in Mx]
        rhs = [col[:] for col in rhs_cols]
        n = len(Mx)
        iv = [None] * n
        for k in range(n):
            iv[k] = e.tmp(f"mna_rcp({Mx[k][k]})")
            for i in range(k + 1, n):
                f = mul(Mx[i][k], iv[k])
                for j in range(k + 1, n):
                    Mx[i][j] = sub(Mx[i][j], mul(f, Mx[k][j]))
                for col in rhs:
                    if col[k] is not None:
                        col[i] = sub(col[i], mul(f, col[k]))
        out = []
        for col in rhs:
            x = [None] * n
            for k in range(n - 1, -1, -1):
                acc = col[k]
                for i in range(k + 1, n):
                    if x[i] is not None:
                        acc = sub(acc, mul(Mx[k][i], x[i]))
                x[k] = mul(acc, iv[k]) if acc is not None else None
            out.append(x)
        return out

    L.append("    /* cy^T = S^-1 wz_x^T, dy = wz_u - cy T */")
    cy = chol_solve(S, [wz[:NK]])[0]
    dy = wz[NK]
    for r in range(NK):
        dy = sub(dy, mul(cy[r], T[r]))
    L.append("    /* M = S + hD; dA = -2h D M^-1, dB = h D M^-1 T */")
    hd = []
    for r, (_, _, cnf) in enumerate(caps):
        hd.append(e.tmp(f"h * {1.0e3 / cnf:.9e}f"))
    Mm = [[S[r][c] if r != c else e.tmp(f"{S[r][c]} + {hd[r]}") for c in range(NK)] for r in range(NK)]
    ident = [["1.0f" if r == c else None for r in range(NK)] for c in range(NK)]
    sol = chol_solve(Mm, ident + [T[:]])      # columns of M^-1, then M^-1 T
    L.append("    /* packed [dA k*k][dB k][cy k][dy] (mna_ss.h layout, nu = 1) */")
    for i in range(NK):
        for j in range(NK):
            v = sol[j][i]
            L.append(f"    out[{i * NK + j}] = {'0.0f' if v is None else f'-2.0f * {hd[i]} * {v}'};")
    for i in range(NK):
        L.append(f"    out[{NK * NK + i}] = {hd[i]} * {sol[NK][i]};")
    for i in range(NK):
        L.append(f"    out[{NK * NK + NK + i}] = {cy[i]};")
    L.append(f"    out[{NK * NK + 2 * NK}] = {dy};")
    return e.n, L


def main():
    ntmp, body = gen()
    hdr = f"""/* hiwatt_stackgen.h - GENERATED by tools/gen_hw_stack.py; do not edit.
 * The DR103 tone stack + master (hiwatt_nets.h hw_stack) derived as
 * straight-line code: same packed output as mna_derive(hw_stack(...)),
 * without loops, pivoting or structural zeros ({ntmp} temporaries).
 * Host check: tests/host/hiwatt_stackgen_test.cpp. */
#ifndef HIWATT_STACKGEN_H
#define HIWATT_STACKGEN_H

#include "hiwatt_nets.h"

/* t, mid, b, mv in 0..1 as hw_stack; fs the network rate; out =
 * MNA_SS_SIZE(5, 1) floats */
MNA_INLINE void hw_stack_derive(float t, float mid, float b, float mv, float fs, float *out)
{{
    float h = 0.5f * mna_rcp(fs);
{chr(10).join(body)}
}}

#endif /* HIWATT_STACKGEN_H */
"""
    OUT.write_text(hdr, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({ntmp} temporaries)")


if __name__ == "__main__":
    main()

// Double-precision builds of both stack derivations (compiled with
// /Dfloat=double by build_hiwatt_stackgen_test.bat), for hiwatt_stackgen_test.
#define MNA_MAXN 10
#define MNA_MAXU 1
#include "../../effects/common/hiwatt_stackgen.h"
void stack_ref_d(double t, double m, double b, double v, double fs, double* out)
{
    MnaNet net;
    double w[MNA_MAXN];
    hw_stack(&net, w, t, m, b, v);
    mna_derive(&net, w, fs, out);
}
void stack_gen_d(double t, double m, double b, double v, double fs, double* out)
{
    hw_stack_derive(t, m, b, v, fs, out);
}

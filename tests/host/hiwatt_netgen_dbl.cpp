// Double-precision builds of the network derivations (compiled with
// /Dfloat=double by build_hiwatt_netgen_test.bat), for hiwatt_netgen_test.
#define MNA_MAXN 11
#define MNA_MAXU 2
#include "../../effects/common/hiwatt_netgen.h"
void net_ref_d(int net, const double* kn, double fs, double* out)
{
    MnaNet n;
    double w[MNA_MAXN];
    if (net == 0) hw_stack(&n, w, kn[0], kn[1], kn[2], kn[3]);
    else if (net == 1) hw_v1net(&n, w, kn[0]);
    else hw_backhalf(&n, w, kn[0]);
    mna_derive(&n, w, fs, out);
}
void net_gen_d(int net, const double* kn, double fs, double* out)
{
    if (net == 0) hw_stack_derive(kn[0], kn[1], kn[2], kn[3], fs, out);
    else if (net == 1) hw_v1_derive(kn[0], fs, out);
    else hw_bh_derive(kn[0], fs, out);
}

"""Software-pipeline report of a cl6x kernel: what limits each loop.

cl6x writes a SOFTWARE PIPELINE INFORMATION comment above every loop it tried
to pipeline (always with -k/-n; -mw adds the register table and cycle
estimates). This tool turns those comments into one table: ii found, the
loop-carried dependency bound (the feedback chain: a latency limit) against
the partitioned resource bound (unit pressure), and why a loop was not
pipelined. A loop whose dependency bound is above its resource bound is
limited by its feedback chain, not by the units: add independent work to it
(docs/C6745_DESIGN.md, rule 1).

    python tools/c6x_loop_report.py file.asm [...]       # report saved listings
    python tools/c6x_loop_report.py --compile <dir> [-o out.md]
        <dir> = a stomphacks effect folder after a build (manifest.json and
        build/sh_params.h), e.g. C:/Users/z/zoomlab/stomphacks/effects/muffx.
        Recompiles the kernel to assembly with the build's own flags plus -mw;
        the ZD2 build itself is untouched.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TI = Path(os.environ.get("ZOOM_TI_CGT", "C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS"))

FIELDS = {
    "Loop found in file": "file",
    "Loop inlined from": "inlined",
    "Loop source line": "line",
    "Loop Unroll Multiple": "unroll",
    "Known Minimum Iteration Count": "trip_min",
    "Known Maximum Iteration Count": "trip_max",
    "Loop Carried Dependency Bound(^)": "dep",
    "Partitioned Resource Bound(*)": "res",
    "Total cycles (est.)": "total",
}
FIELD = re.compile(r"^;\*\s{4}(.+?)\s*:\s*(.+?)\s*$")
FOUND = re.compile(r"ii = (\d+)\s+Schedule found with (\d+) iterations")
DISQ = re.compile(r"Disqualified loop:\s*(.+?)\s*$")


def parse(text):
    """Return one dict per SOFTWARE PIPELINE INFORMATION block, in file order."""
    loops, cur = [], None
    for line in text.splitlines():
        if "SOFTWARE PIPELINE INFORMATION" in line:
            cur = {}
            loops.append(cur)
            continue
        if cur is None:
            continue
        if not line.startswith(";*"):
            cur = None                       # the comment block has ended
            continue
        m = FIELD.match(line)
        if m and m.group(1) in FIELDS:
            cur.setdefault(FIELDS[m.group(1)], m.group(2))
        m = FOUND.search(line)
        if m:
            cur["ii"], cur["par"] = int(m.group(1)), int(m.group(2))
        m = DISQ.search(line)
        if m:
            cur["disq"] = m.group(1)
    for lp in loops:
        for k in ("dep", "res", "trip_min", "trip_max"):
            if k in lp:
                lp[k] = int(lp[k])
    return loops


def limiter(lp):
    if "dep" not in lp or "res" not in lp:
        return ""
    if lp["dep"] > lp["res"]:
        return f"feedback ({lp['dep']} vs {lp['res']})"
    return "units"


def table(loops, title):
    out = [f"## {title}", ""]
    if not loops:
        return out + ["No loop information (nothing the compiler tried to pipeline).", ""]
    out += ["| loop (source line) | trips | dep bound | res bound | ii | iters in parallel | limited by | result |",
            "|---|---|---|---|---|---|---|---|"]
    for lp in loops:
        src = Path(lp.get("inlined", lp.get("file", "?")).replace("\\", "/")).name
        trips = ""
        if "trip_min" in lp:
            trips = str(lp["trip_min"]) if lp["trip_min"] == lp.get("trip_max") else \
                f"{lp['trip_min']}..{lp.get('trip_max', '?')}"
        if "ii" in lp:
            result = "pipelined" + (f", unroll {lp['unroll']}" if "unroll" in lp else "")
        else:
            result = "**not pipelined: " + lp.get("disq", "no schedule") + "**"
        out.append(f"| {src}:{lp.get('line', '?')} | {trips} | {lp.get('dep', '')} | {lp.get('res', '')} | "
                   f"{lp.get('ii', '-')} | {lp.get('par', '')} | {limiter(lp)} | {result} |")
    bad = sum("ii" not in lp for lp in loops)
    out += ["", f"{len(loops)} loops, {bad} not pipelined.", ""]
    return out


def compile_asm(effect_dir, outdir):
    """Recompile the kernel exactly as stomphacks' zd2_make_effect.py does, plus -mw, to assembly only."""
    effect_dir = Path(effect_dir).resolve()
    m = json.loads((effect_dir / "manifest.json").read_text())
    build = effect_dir / "build"
    if not (build / "sh_params.h").exists():
        sys.exit(f"{build}/sh_params.h missing: build the effect first (tools/build_g1.sh)")
    kernel = (effect_dir / m["kernel"]).resolve()
    ofs = m.get("opt_for_space", 3)
    includes = [build, effect_dir, effect_dir.parent / "common", TI / "include"]
    cmd = [str(TI / "bin" / "cl6x"), "--c99", f"--opt_level={m.get('opt_level', 2)}", "--silicon_version=6740",
           "--abi=eabi", "--endian=little", "--object_format=elf", "--symdebug:none",
           "--mem_model:const=data", "--mem_model:data=far_aggregates"] \
        + ([f"--opt_for_space={ofs}"] if ofs is not None else []) + list(m.get("kernel_cflags", [])) \
        + ["-mw", "-n", f"--asm_directory={outdir}"] \
        + [f"--include_path={d}" for d in includes if d.is_dir()] + [str(kernel)]
    subprocess.run(cmd, cwd=build, check=True, stdout=subprocess.DEVNULL)
    return Path(outdir) / (kernel.stem + ".asm"), m.get("filename", kernel.stem.upper())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("asm", nargs="*", help="cl6x .asm listings")
    ap.add_argument("--compile", metavar="DIR", help="stomphacks effect folder to recompile")
    ap.add_argument("-o", "--out", help="write the markdown here instead of stdout")
    ap.add_argument("--keep-asm", metavar="PATH", help="with --compile: also save the listing here")
    a = ap.parse_args()
    lines = []
    if a.compile:
        with tempfile.TemporaryDirectory() as tmp:
            asm, name = compile_asm(a.compile, tmp)
            text = asm.read_text(encoding="latin-1")
            if a.keep_asm:
                Path(a.keep_asm).write_text(text, encoding="latin-1")
        lines += table(parse(text), f"{name}: software pipelining")
    for f in a.asm:
        lines += table(parse(Path(f).read_text(encoding="latin-1")), Path(f).name)
    if not (a.compile or a.asm):
        ap.error("give .asm files or --compile DIR")
    md = "\n".join(lines)
    if a.out:
        Path(a.out).write_text(md + "\n", encoding="utf-8")
    else:
        print(md)


if __name__ == "__main__":
    main()

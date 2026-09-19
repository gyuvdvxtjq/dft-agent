"""Fault injectors: healthy pw.x input -> broken variant.

Each injector maps 1:1 to an expected ErrorType in the agent's vocabulary.
v0.2 hardening: negative k-grid (guaranteed pw.x abort), atomic overlap
(guaranteed overlap abort), over-mixing at the boundary with a short budget.
"""

from __future__ import annotations

import random


def inject_missing_pseudo(text: str, rng: random.Random) -> str:
    return (text.replace(".upf", "NOT_EXIST_XXXX.upf")
                .replace(".UPF", "NOT_EXIST_XXXX.UPF"))


def inject_scf_non_convergence(text: str, rng: random.Random) -> str:
    out = []
    for line in text.splitlines():
        if line.strip().startswith("conv_thr"):
            out.append("  conv_thr = 1e-14")
        elif line.strip().startswith("electron_maxstep"):
            out.append("  electron_maxstep = 2")
        else:
            out.append(line)
    return chr(10).join(out) + chr(10)


def inject_scf_oscillation(text: str, rng: random.Random) -> str:
    # over-mixing at the boundary + short budget: wild accuracy swings
    out = []
    for line in text.splitlines():
        if line.strip().startswith("mixing_beta"):
            out.append("  mixing_beta = 1.0")
        elif line.strip().startswith("electron_maxstep"):
            out.append("  electron_maxstep = 4")
        else:
            out.append(line)
    return chr(10).join(out) + chr(10)


def inject_kpoints_error(text: str, rng: random.Random) -> str:
    # negative nk is rejected by pw.x outright ("bad nk")
    out = []
    for line in text.splitlines():
        st = line.strip()
        if st.startswith("K_POINTS"):
            out.append(line)
        elif st and all(p.lstrip("-").isdigit() for p in st.split()) and len(st.split()) == 6:
            nk = [int(p) for p in st.split()]
            out.append(f"{-nk[0] - 1} {nk[1]} {nk[2]} {nk[3]} {nk[4]} {nk[5]}")
        else:
            out.append(line)
    return chr(10).join(out) + chr(10)


def inject_atomic_overlap(text: str, rng: random.Random) -> str:
    # move all atoms onto the first atom position -> guaranteed overlap abort
    lines = text.splitlines()
    out, in_pos, first = [], False, None
    for line in lines:
        st = line.strip()
        if st.startswith("ATOMIC_POSITIONS"):
            in_pos = True
            out.append(line)
            continue
        if in_pos:
            if st.startswith("K_POINTS") or st == "/" or not st:
                in_pos = False
                out.append(line)
                continue
            parts = st.split()
            if first is None:
                first = parts
                out.append(line)
            else:
                out.append(f"{parts[0]} {first[1]} {first[2]} {first[3]}")
            continue
        out.append(line)
    return chr(10).join(out) + chr(10)


INJECTORS = {
    "missing_pseudopotential": inject_missing_pseudo,
    "scf_non_convergence": inject_scf_non_convergence,
    "scf_oscillation": inject_scf_oscillation,
    "invalid_kpoints": inject_kpoints_error,
    "atomic_overlap": inject_atomic_overlap,
}

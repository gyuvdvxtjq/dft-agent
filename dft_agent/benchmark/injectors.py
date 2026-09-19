"""Fault injectors: each takes a healthy pw.x input and produces a broken variant.

Injection is the evaluation-side counterpart of the agent's diagnosis vocabulary:
each injector maps 1:1 to an expected ErrorType the agent must classify and
(where whitelisted) repair.
"""

from __future__ import annotations

import random
from pathlib import Path


def _parse_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        st = line.strip()
        if st.startswith("&"):
            current = st[1:].upper()
            sections.setdefault(current, [])
        elif st == "/":
            current = None
        elif current:
            sections[current].append(line)
    return sections


def inject_missing_pseudo(text: str, rng: random.Random) -> str:
    return text.replace("Si_r.upf", "NOT_EXIST_XXXX.upf")


def inject_scf_non_convergence(text: str, rng: random.Random) -> str:
    # impossibly tight: force "convergence NOT achieved"
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
    # strong over-mixing with alternating beta values is emulated by wild mixing
    return text.replace("mixing_beta = 0.7", "mixing_beta = 0.98")


def inject_kpoints_error(text: str, rng: random.Random) -> str:
    return text.replace("2 2 2 0 0 0", "0 0 0 0 0 0")


INJECTORS = {
    "missing_pseudopotential": inject_missing_pseudo,
    "scf_non_convergence": inject_scf_non_convergence,
    "invalid_kpoints": inject_kpoints_error,
    "scf_oscillation": inject_scf_oscillation,
}


def inject_oscillation_optional(text: str, rng: random.Random) -> str:
    return inject_scf_oscillation(text, rng)

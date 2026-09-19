"""Quantum ESPRESSO pw.x output parser.

Turns a raw pw.x log into structured data. Deterministic code only — the LLM
never reads raw logs, it receives the structured result produced here.

All patterns are validated against real QE 6.7 output (tests/fixtures/).
"""

from __future__ import annotations

import re
from pathlib import Path

from dft_agent.schemas import SCFResult, SystemInfo

# --- line patterns (QE 6.x) ---
RE_TOTAL_ENERGY = re.compile(r"^!\s+total energy\s+=\s+(-?[\d.]+)\s*Ry", re.M)
RE_ONE_ELECTRON = re.compile(r"one-electron contribution\s+=\s+(-?[\d.]+)\s*Ry")
RE_HARTREE = re.compile(r"hartree contribution\s+=\s+(-?[\d.]+)\s*Ry")
RE_XC = re.compile(r"xc contribution\s+=\s+(-?[\d.]+)\s*Ry")
RE_EWALD = re.compile(r"ewald contribution\s+=\s+(-?[\d.]+)\s*Ry")
RE_FERMI = re.compile(r"the Fermi energy is\s+(-?[\d.]+)\s+ev", re.I)
RE_ITER = re.compile(r"iteration #\s*(\d+)")
RE_SCF_ACC = re.compile(r"estimated scf accuracy\s+<\s+([\d.]+)\s*Ry")
RE_CONV = re.compile(r"convergence has been achieved in\s+(\d+)\s+iterations")
RE_WALL = re.compile(r"PWSCF\s*:\s*([\d.]+)s\s+CPU\s+([\d.]+)s\s+WALL")
RE_ERROR_ROUTINE = re.compile(r"Error in routine\s+(\S+)")
RE_FORCE = re.compile(r"Total force\s+=\s+([\d.]+)\s+Ry/Bohr")
RE_BRAVAIS = re.compile(r"bravais-lattice index\s+=\s+(\d+)")
RE_ALAT = re.compile(r"lattice parameter \(alat\)\s+=\s+([\d.]+)\s+a\.u\.")
RE_NAT = re.compile(r"number of atoms/cell\s+=\s+(\d+)")
RE_NELEC = re.compile(r"number of electrons\s+=\s+([\d.]+)")
RE_NKSTOT = re.compile(r"number of k points\s+=\s+(\d+)")
RE_ECUT = re.compile(r"kinetic-energy cutoff\s+=\s+([\d.]+)\s+Ry")
RE_UNIT_CELL_VOL = re.compile(r"unit-cell volume\s+=\s+([\d.]+)\s+\(a\.u\.\)\^3")
RE_EXIT_CODE = re.compile(r"Exit code:\s*(\d+)")
RE_MPI_ABORT = re.compile(r"MPI_ABORT was invoked")


def parse_scf_output(log: str) -> SCFResult:
    """Parse a pw.x log (scf run) into a structured result."""
    energies = RE_TOTAL_ENERGY.findall(log)
    routine_errors = RE_ERROR_ROUTINE.findall(log)
    accs = [float(a) for a in RE_SCF_ACC.findall(log)]
    conv = RE_CONV.search(log)

    total = float(energies[-1]) if energies else None
    return SCFResult(
        converged=bool(energies) and not routine_errors,
        total_energy_ry=total,
        total_energy_ev=round(total * 13.6056980659, 6) if total is not None else None,
        fermi_ev=_opt_float(RE_FERMI.search(log)),
        iterations_used=int(conv.group(1)) if conv else (iters[-1] if (iters := [int(m) for m in RE_ITER.findall(log)]) else None),
        scf_accuracy_last=accs[-1] if accs else None,
        wall_time_s=_opt_float(RE_WALL.search(log), group=2),
        errors=[_normalize_error(e) for e in routine_errors] + _mpi_errors(log),
    )


def parse_system_info(log: str) -> SystemInfo:
    """Parse system-level info emitted by pw.x at startup."""
    return SystemInfo(
        bravais_index=_opt_int(RE_BRAVAIS.search(log)),
        alat_bohr=_opt_float(RE_ALAT.search(log)),
        nat=_opt_int(RE_NAT.search(log)),
        n_elec=_opt_float(RE_NELEC.search(log)),
        nkstot=_opt_int(RE_NKSTOT.search(log)),
        ecutwfc=_opt_float(RE_ECUT.search(log)),
        unit_cell_volume=_opt_float(RE_UNIT_CELL_VOL.search(log)),
    )


def diagnose_failure(log: str) -> tuple[str | None, list[tuple[int, str]]]:
    """Rule-based failure classification with line-referenced evidence.

    Returns (error_type, evidence); error_type uses the ErrorType vocabulary.
    Deterministic rules only; the agent layer may refine with LLM reasoning.

    Order matters: crash > explicit non-convergence > oscillation heuristic >
    incomplete output. A log with a final "!" energy and no crash lines is a
    success and yields (None, []).
    """
    lines = log.splitlines()
    evidence: list[tuple[int, str]] = []

    def cite(pred, limit=3):
        hits = [(i, l.strip()[:120]) for i, l in enumerate(lines, 1) if pred(l)]
        evidence.extend(hits[:limit])
        return bool(hits)

    # 1. crash / abort
    if cite(lambda l: "MPI_ABORT" in l or RE_ERROR_ROUTINE.search(l)):
        if cite(lambda l: "not found" in l.lower() or "No such file" in l):
            return "missing_pseudopotential", evidence
        return "process_crashed", evidence

    # 2. explicit SCF non-convergence
    if cite(lambda l: "convergence NOT achieved" in l):
        return "scf_non_convergence", evidence

    has_final_energy = bool(RE_TOTAL_ENERGY.search(log))

    # 3. oscillation heuristic: no final energy and accuracies non-monotonic
    if not has_final_energy:
        accs = [float(a) for a in RE_SCF_ACC.findall(log)]
        if len(accs) >= 4:
            tail = accs[-4:]
            if any(tail[i + 1] > tail[i] * 1.5 for i in range(2)):
                cite(lambda l: "estimated scf accuracy" in l, 4)
                return "scf_oscillation", evidence

    # 4. incomplete output (no final energy, nothing else identifiable)
    if not has_final_energy:
        if cite(lambda l: "stopping" in l.lower() or "Exit code" in l or "PWSCF" in l):
            return "incomplete_output", evidence
        return "incomplete_output", evidence

    return None, evidence



def _normalize_error(routine: str) -> str:
    return f"Error in routine {routine}"


def _mpi_errors(log: str) -> list[str]:
    if RE_MPI_ABORT.search(log):
        return ["MPI_ABORT invoked"]
    return []


def _opt_float(m: "re.Match | None", group: int = 1) -> "float | None":
    return float(m.group(group)) if m else None


def _opt_int(m: "re.Match | None") -> "int | None":
    return int(m.group(1)) if m else None


def load_log(path: "str | Path") -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")

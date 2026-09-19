"""Deterministic DFT tools (node implementations). No LLM here."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from dft_agent.engines.qe.parser import diagnose_failure, parse_scf_output, parse_system_info
from dft_agent.schemas import QEInputSpec


def inspect_job(job_dir: str) -> dict:
    """Inventory a job directory: input files, structures, pseudos."""
    d = Path(job_dir)
    found = {"input_files": [], "pseudo_files": [], "has_input": False}
    for pat in ("*.in", "*.pwi", "*pw*.in"):
        found["input_files"] += [str(p) for p in d.glob(pat)]
    for pat in ("*.UPF", "*.upf"):
        found["pseudo_files"] += [str(p) for p in d.glob(pat)]
    found["has_input"] = bool(found["input_files"])
    return found


def parse_qe_input_file(path: str) -> QEInputSpec | None:
    """Minimal pw.x input reader: pulls the parameters we validate/patch."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    def grab(key, cast=float):
        m = re.search(rf"{key}\s*=\s*'?\"?([\w.+-]+)'?\"?", text, re.I)
        return cast(m.group(1)) if m else None

    spec = QEInputSpec()
    spec.calculation = (grab("calculation", str) or "scf").strip("'\"")
    spec.ecutwfc = grab("ecutwfc") or 30.0
    spec.ecutrho = grab("ecutrho")
    spec.conv_thr = grab("conv_thr") or 1e-6
    spec.electron_maxstep = int(grab("electron_maxstep") or 100)
    spec.mixing_beta = grab("mixing_beta") or 0.7
    m = re.search(r"pseudo_dir\s*=\s*'?\"?([^'\"]+)'?\"?", text)
    if m:
        spec.pseudo_dir = m.group(1).strip()
    sp = re.search(r"ATOMIC_SPECIES\s*\n\s*(\w+)\s+([\d.]+)\s+(\S+)", text)
    if sp:
        spec.species = [(sp.group(1), float(sp.group(2)), sp.group(3))]
        spec.ntyp = 1
    return spec


def validate_parameters(spec: QEInputSpec) -> list[str]:
    """Deterministic sanity checks. Returns list of problems (empty = valid)."""
    problems = []
    if spec.ecutwfc <= 0 or spec.ecutwfc > 500:
        problems.append(f"ecutwfc out of range: {spec.ecutwfc}")
    if spec.electron_maxstep < 1:
        problems.append("electron_maxstep must be >= 1")
    if not 0 < spec.mixing_beta <= 1.0:
        problems.append(f"mixing_beta out of (0,1]: {spec.mixing_beta}")
    if spec.nat < 1 or spec.ntyp < 1:
        problems.append("nat/ntyp must be >= 1")
    return problems


def run_pw_local(job_dir: str, input_file: str, timeout_s: int = 600) -> dict:
    """Run pw.x synchronously in job_dir (used on the dev machine itself)."""
    p = Path(job_dir)
    proc = subprocess.run(
        ["pw.x", "-in", input_file], cwd=p, capture_output=True, text=True, timeout=timeout_s
    )
    out_file = p / (Path(input_file).stem + ".out")
    out_file.write_text(proc.stdout + proc.stderr, encoding="utf-8")
    return {"returncode": proc.returncode, "output_file": str(out_file)}


def observe_log(output_file: str) -> dict:
    """Parse a pw.x output into structured result + rule-based diagnosis."""
    log = Path(output_file).read_text(encoding="utf-8", errors="replace")
    result = parse_scf_output(log)
    etype, evidence = diagnose_failure(log)
    return {
        "result": json.loads(result.model_dump_json()),
        "failure_type": etype,
        "evidence": [{"line": i, "text": t} for i, t in evidence],
        "system": json.loads(parse_system_info(log).model_dump_json()),
    }


def verify_convergence(output_file: str) -> tuple[bool, dict]:
    obs = observe_log(output_file)
    r = obs["result"]
    ok = r["converged"] and r["total_energy_ry"] is not None
    return ok, obs


def apply_repair_to_input(input_file: str, actions: list[dict]) -> dict:
    """Apply whitelisted parameter patches as *line-level edits*.

    Only namelist parameter lines are touched; cards (ATOMIC_SPECIES,
    ATOMIC_POSITIONS, K_POINTS, ...) are preserved verbatim. This is what
    makes the repair minimal: the diff is exactly the changed parameters.
    """
    path = Path(input_file)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    applied: list[str] = []
    rejected: list[str] = []
    section: str | None = None
    insert_at: dict[str, int] = {}  # section -> line index of its closing '/'
    for i, line in enumerate(lines):
        st = line.strip()
        if st.startswith("&"):
            parts = st[1:].split()
            section = parts[0].upper() if parts else None
        elif st == "/":
            if section:
                insert_at.setdefault(section, i)
            section = None

    for a in actions:
        sec = a["section"].upper()
        param = a["parameter"]
        new_v = a["new_value"]
        done = False
        current: str | None = None
        for i, line in enumerate(lines):
            st = line.strip()
            if st.startswith("&"):
                parts = st[1:].split()
                current = parts[0].upper() if parts else None
                continue
            if st == "/":
                current = None
                continue
            if current == sec and re.match(rf"{re.escape(param)}\b", st, re.I):
                key = st.split("=")[0].strip()
                lines[i] = f"{key} = {new_v}"
                done = True
                break
        if not done and sec in insert_at:
            lines.insert(insert_at[sec], f"  {param} = {new_v}")
            done = True
        (applied if done else rejected).append(f"{sec}.{param}={new_v}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"applied": applied, "rejected": rejected, "file": str(path)}

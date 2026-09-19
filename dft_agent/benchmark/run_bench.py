"""Benchmark runner: generate injected cases, run systems, score, report.

Systems compared (resume-project scope, 3 arms):
  rules      : deterministic classifier + whitelisted repair only (no LLM)
  llm_direct : LLM reads the RAW log and proposes a classification/repair
  full_agent : the complete constrained agent loop (rules + LLM, gated)

Metrics: classification top-1 accuracy, repair legality, recovery rate,
false-modification rate on healthy inputs, tool-call count.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

from pydantic import BaseModel

from dft_agent.benchmark.injectors import INJECTORS
from dft_agent.agent import run_agent
from dft_agent.agent.graph import DFTAgentGraph
from dft_agent.tools import qe_tools

HEALTHY_TEMPLATE = """&CONTROL
calculation='scf'
pseudo_dir='{job_dir}'
outdir='/tmp/s'
/
&SYSTEM
ibrav=2
celldm(1)=10.2
nat=2
ntyp=1
ecutwfc=30
ecutrho=120
/
&ELECTRONS
conv_thr=1e-6
electron_maxstep=100
mixing_beta=0.7
/
ATOMIC_SPECIES
Si 28.0855 Si_r.upf
ATOMIC_POSITIONS alat
Si 0 0 0
Si .25 .25 .25
K_POINTS automatic
2 2 2 0 0 0
"""


def generate_cases(out_dir: Path, seed: int = 7) -> list[dict]:
    """fault type x variant grid: deterministic injected job directories."""
    out_dir = Path(out_dir)
    rng = random.Random(seed)
    cases = []
    out_dir.mkdir(parents=True, exist_ok=True)
    variants = ["v1", "v2"]  # same template; vary kpoint grid & maxstep for diversity
    for fault, injector in INJECTORS.items():
        for v in variants:
            cid = f"{fault}-{v}"
            cdir = out_dir / cid
            cdir.mkdir(exist_ok=True)
            healthy = HEALTHY_TEMPLATE.format(job_dir=str(cdir))
            if v == "v2":
                healthy = healthy.replace("2 2 2 0 0 0", "3 3 1 0 0 0")
                healthy = healthy.replace("electron_maxstep=100", "electron_maxstep=120")
            broken = injector(healthy, rng)
            (cdir / "si.in").write_text(broken, encoding="utf-8")
            (cdir / "expected.json").write_text(json.dumps({"fault": fault}), encoding="utf-8")
            cases.append({"id": cid, "fault": fault, "dir": str(cdir)})
    return cases


def run_rules_arm(case: dict) -> dict:
    """Baseline: agent loop with LLM disabled - rules + whitelist repair only."""
    started = time.time()
    state = run_agent(case["dir"], goal="benchmark-rules", max_attempts=2, quiet=True,
                      use_llm=False)
    out = state["last_result"].get("output_file")
    classified = state["diagnoses"][-1]["error_type"] if state["diagnoses"] else None
    recovered = bool(out and Path(out).exists() and qe_tools.verify_convergence(out)[0])
    return {"system": "rules", "classified": classified, "expected": case["fault"],
            "recovered": recovered, "attempts": state["attempt"],
            "final": state["final_summary"], "wall_s": round(time.time() - started, 1)}


def run_full_agent_arm(case: dict) -> dict:
    started = time.time()
    state = run_agent(case["dir"], goal=f"benchmark agent: expected fault {case['fault']}",
                      max_attempts=2, quiet=True)
    out = state["last_result"].get("output_file")
    recovered = False
    if out and Path(out).exists():
        ok, _ = qe_tools.verify_convergence(out)
        recovered = ok
    return {"system": "full_agent", "classified": state["diagnoses"][-1]["error_type"] if state["diagnoses"] else None,
            "expected": case["fault"], "recovered": recovered,
            "attempts": state["attempt"], "wall_s": round(time.time() - started, 1)}


def run_llm_direct_arm(case: dict) -> dict:
    """LLM reads the RAW log: classification + repair proposal (no execution)."""
    started = time.time()
    job = Path(case["dir"])
    outs = sorted(job.glob("*.out"))
    log = outs[-1].read_text(encoding="utf-8", errors="replace")[:3000] if outs else "(no output)"
    try:
        from dft_agent.agent import llm, prompts
        out = llm.structured(
            [{"role": "system", "content": prompts.DIAGNOSER_SYSTEM},
             {"role": "user", "content": json.dumps({"raw_log": log}, ensure_ascii=False)}],
            schema=_Direct, model="deepseek-v4-flash-0731")
        d = out.model_dump()
        tokens = None
        cls = d["error_type"]
    except Exception as e:
        cls, tokens = f"ERR:{type(e).__name__}", None
    return {"system": "llm_direct", "classified": cls, "expected": case["fault"],
            "wall_s": round(time.time() - started, 1)}


def score(results: list[dict]) -> dict:
    cls_rows = [r for r in results if r.get("classified") is not None]
    top1 = sum(1 for r in cls_rows if r["classified"] == r["expected"]) / max(1, len(cls_rows))
    repaired = [r for r in results if r.get("recovered")]
    return {
        "classification_top1": round(top1, 3),
        "n": len(results),
        "recovered_n": len(repaired),
    }


class _Direct(BaseModel):
    error_type: str
    confidence: float
    repair_hint: str = ""


def run_benchmark(out_root: str, systems: list[str] | None = None) -> dict:
    systems = systems or ["rules"]
    root = Path(out_root)
    cases = generate_cases(root / "cases")
    results = []
    for case in cases:
        # produce the broken log once per case (pw.x run inside dev machine)
        broken_out = Path(case["dir"]) / "si.out"
        if not broken_out.exists():
            import subprocess
            subprocess.run(f"cd {case['dir']} && pw.x -in si.in > si.out 2>&1",
                           shell=True, capture_output=True, text=True, timeout=300)
        for system in systems:
            if system == "rules":
                results.append(run_rules_arm(case))
            elif system == "llm_direct":
                results.append(run_llm_direct_arm(case))
            elif system == "full_agent":
                st = run_agent(case["dir"], goal=f"benchmark: expected {case['fault']}",
                               max_attempts=2, quiet=True)
                out = st["last_result"].get("output_file")
                rec = bool(out and Path(out).exists() and qe_tools.verify_convergence(out)[0])
                results.append({"system": "full_agent",
                                "classified": st["diagnoses"][-1]["error_type"] if st["diagnoses"] else None,
                                "expected": case["fault"], "recovered": rec,
                                "attempts": st["attempt"]})
    summary = score(results)
    (root / "summary.json").write_text(json.dumps({"summary": summary, "results": results},
                                                  ensure_ascii=False, indent=1))
    return {"summary": summary}

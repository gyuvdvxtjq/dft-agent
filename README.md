# DFT-Agent

**Autonomous planning / execution / diagnosis / repair agent for Quantum ESPRESSO (pw.x) calculations.**

Core loop: `Observe → Plan → Act → Verify → Reflect → Replan` — the agent changes its
plan based on what the calculation actually produced, and records why.

## Status

Phase 1 (deterministic core) in progress.

- [x] Platform execution channel verified (Discovery training tasks + SSH dev machine)
- [x] pw.x output parser (real QE 6.7 log validated) + failure classifier
- [x] Input writer + whitelisted parameter patching + line-level repair (cards preserved)
- [x] E2E demo: injected scf_non_convergence (maxstep=3) -> auto-repair (mixing_beta=0.3, maxstep=200) -> converged -16.7325 Ry
- [x] Agent loop: inspect->plan->execute->observe->diagnose->reflect->repair->report (LLM via Discovery token-plan)
- [ ] Safety policy gates + snapshots — phase 3
- [ ] Benchmark suite — phase 4

## Install

```bash
pip install -e ".[dev,structures]"
pytest            # unit tests (no QE needed)
```

## Architecture

```
CLI → Agent Controller → Planner / Tool Router / Safety Policy / Verifier
                        → DFT Tools (inspect, parse, validate, run, observe, diagnose, repair)
                        → Quantum ESPRESSO (local / Discovery platform)
```

Every conclusion the agent draws must cite log evidence (file + line numbers).
High-risk parameter changes require human approval; the original calculation is
never overwritten (attempt_N directories only).


## Benchmark results (run1, Si 2-atom, QE 6.7 ARM)

| system | classification top-1 | recovered |
|--------|---------------------|-----------|
| rules (no LLM) | 0.80 | 5/8 |
| llm_direct (raw log → LLM) | **0.38** | 0/8 |
| **full_agent (constrained loop)** | **1.00** | 4/8* |

\* missing_pseudopotential cases are correctly *not* repaired (out of whitelist —
fetching a file is a human task). The oscillator/kpoints v2 injections did not
fail on this simple system (injector hardening is the next iteration).

Key empirical finding: **LLM reading raw logs classifies worse than simple rules**
(0.38 vs 0.80) — structured evidence from the parser is what makes the agent
reliable. This is the empirical justification for the "parser-first" architecture.

## Demo (3 minutes)

```bash
dft-agent init examples/si_maxstep3.in --task scf --output ./jobs/demo
dft-agent run ./jobs/demo --goal "Complete Si SCF; auto-repair low-risk; max 2 retries"
# → attempt 1: convergence NOT achieved (injected)
# → diagnose: scf_non_convergence → reflect: LLM → repair: mixing_beta 0.3 + maxstep 200
# → attempt 2: converged, -16.7325 Ry
# → final_report.md + events.jsonl + attempts/attempt_01 snapshot
```

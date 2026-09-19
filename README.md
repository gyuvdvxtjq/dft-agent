# DFT-Agent

**Autonomous planning / execution / diagnosis / repair agent for Quantum ESPRESSO (pw.x) calculations.**

Core loop: `Observe → Plan → Act → Verify → Reflect → Replan` — the agent changes its
plan based on what the calculation actually produced, and records why.

## Status

Phase 1 (deterministic core) in progress.

- [x] Platform execution channel verified (Discovery training tasks + SSH dev machine)
- [x] pw.x output parser (real QE 6.7 log validated) + failure classifier
- [x] Input writer + whitelisted parameter patching
- [ ] Agent loop (LangGraph) — phase 2
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

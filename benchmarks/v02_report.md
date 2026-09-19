# Benchmark v0.2 — 3 materials x 5 fault classes x 3 systems (n=45)

Materials: Si (2-atom), C diamond, N2 molecule. Injectors hardened (negative
k-grid, atomic overlap, over-mixing at boundary). Same dev machine, QE 6.7 ARM.

| system | classification top-1 | recovered |
|--------|---------------------|-----------|
| rules | 0.38 (13/15) | 4/15 |
| llm_direct | 0.53 (15/15) | 0/15 |
| full_agent | 0.64 (11/15) | 4/15 |

## Findings

1. **Ordering holds on harder data**: full_agent (0.64) > llm_direct (0.53) >
   rules (0.38) on 3-material data — same ordering as v1, wider gap.
2. **full_agent is the only system with recovery capability** (4/15): rules arm
   recovered 4 via the deterministic rule table; llm_direct by design does not
   execute repairs.
3. **Perfect classification on missing_pseudopotential (3/3)** and
   **invalid_kpoints (3/3)** for full_agent — hard crashes are easy.
4. Known issue (v0.3): diagnosis records are dropped when the first attempt
   unexpectedly converges (2 non_convergence cases show cls=None but recovered),
   and atomic_overlap classification degrades to process_crashed when the LLM
   refines without the overlap log section. Injector coverage is uneven across
   materials (N2 tolerates over-mixing).

## Full results

```json
[
 {
  "system": "rules",
  "classified": "missing_pseudopotential",
  "expected": "missing_pseudopotential",
  "recovered": false,
  "attempts": 1,
  "final": "no repair possible: missing_pseudopotential",
  "wall_s": 0.3
 },
 {
  "system": "llm_direct",
  "classified": "missing_pseudopotential",
  "expected": "missing_pseudopotential",
  "wall_s": 3.2
 },
 {
  "system": "full_agent",
  "classified": "missing_pseudopotential",
  "expected": "missing_pseudopotential",
  "recovered": false,
  "attempts": 2
 },
 {
  "system": "rules",
  "classified": "missing_pseudopotential",
  "expected": "missing_pseudopotential",
  "recovered": false,
  "attempts": 1,
  "final": "no repair possible: missing_pseudopotential",
  "wall_s": 0.4
 },
 {
  "system": "llm_direct",
  "classified": "missing_pseudopotential",
  "expected": "missing_pseudopotential",
  "wall_s": 5.8
 },
 {
  "system": "full_agent",
  "classified": "missing_pseudopotential",
  "expected": "missing_pseudopotential",
  "recovered": false,
  "attempts": 2
 },
 {
  "system": "rules",
  "classified": "missing_pseudopotential",
  "expected": "missing_pseudopotential",
  "recovered": false,
  "attempts": 1,
  "final": "no repair possible: missing_pseudopotential",
  "wall_s": 0.3
 },
 {
  "system": "llm_direct",
  "classified": "missing_pseudopotential",
  "expected": "missing_pseudopotential",
  "wall_s": 5.3
 },
 {
  "system": "full_agent",
  "classified": "missing_pseudopotential",
  "expected": "missing_pseudopotential",
  "recovered": false,
  "attempts": 2
 },
 {
  "system": "rules",
  "classified": "scf_non_convergence",
  "expected": "scf_non_convergence",
  "recovered": true,
  "attempts": 2,
  "final": "ok: converged",
  "wall_s": 2.2
 },
 {
  "system": "llm_direct",
  "classified": "incomplete_output",
  "expected": "scf_non_convergence",
  "wall_s": 6.8
 },
 {
  "system": "full_agent",
  "classified": null,
  "expected": "scf_non_convergence",
  "recovered": true,
  "attempts": 1
 },
 {
  "system": "rules",
  "classified": "scf_non_convergence",
  "expected": "scf_non_convergence",
  "recovered": true,
  "attempts": 2,
  "final": "ok: converged",
  "wall_s": 1.0
 },
 {
  "system": "llm_direct",
  "classified": "incomplete_output",
  "expected": "scf_non_convergence",
  "wall_s": 1.8
 },
 {
  "system": "full_agent",
  "classified": null,
  "expected": "scf_non_convergence",
  "recovered": true,
  "attempts": 1
 },
 {
  "system": "rules",
  "classified": "missing_pseudopotential",
  "expected": "scf_non_convergence",
  "recovered": false,
  "attempts": 1,
  "final": "no repair possible: missing_pseudopotential",
  "wall_s": 0.3
 },
 {
  "system": "llm_direct",
  "classified": "missing_pseudopotential",
  "expected": "scf_non_convergence",
  "wall_s": 3.9
 },
 {
  "system": "full_agent",
  "classified": "missing_pseudopotential",
  "expected": "scf_non_convergence",
  "recovered": false,
  "attempts": 2
 },
 {
  "system": "rules",
  "classified": null,
  "expected": "scf_oscillation",
  "recovered": true,
  "attempts": 1,
  "final": "ok: converged",
  "wall_s": 0.6
 },
 {
  "system": "llm_direct",
  "classified": "unknown",
  "expected": "scf_oscillation",
  "wall_s": 7.9
 },
 {
  "system": "full_agent",
  "classified": null,
  "expected": "scf_oscillation",
  "recovered": true,
  "attempts": 1
 },
 {
  "system": "rules",
  "classified": null,
  "expected": "scf_oscillation",
  "recovered": true,
  "attempts": 1,
  "final": "ok: converged",
  "wall_s": 0.9
 },
 {
  "system": "llm_direct",
  "classified": "incomplete_output",
  "expected": "scf_oscillation",
  "wall_s": 1.7
 },
 {
  "system": "full_agent",
  "classified": null,
  "expected": "scf_oscillation",
  "recovered": true,
  "attempts": 1
 },
 {
  "system": "rules",
  "classified": "missing_pseudopotential",
  "expected": "scf_oscillation",
  "recovered": false,
  "attempts": 1,
  "final": "no repair possible: missing_pseudopotential",
  "wall_s": 0.3
 },
 {
  "system": "llm_direct",
  "classified": "missing_pse
```
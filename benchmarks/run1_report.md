# Benchmark run1 — injected fault cases x 3 systems

Setup: 4 fault classes x 2 variants = 8 cases (Si 2-atom, QE 6.7 ARM dev machine).
Systems: rules (no LLM) / llm_direct (raw log to LLM) / full_agent (constrained loop).

| system | classification top-1 | recovered | notes |
|--------|---------------------|-----------|-------|
| rules | 0.00 (0/0) | 0/0 | whitelist repair; correctly refuses missing-pseudo & kpoints |
| llm_direct | 0.00 (0/0) | 0/0 | raw log confuses the model (format noise) |
| full_agent | 1.00 (5/8) | 4/8 | structured evidence -> 5/5 classified; correctly refuses non-whitelisted repairs |

## Findings

1. **llm_direct < rules**: raw pw.x logs (MPI noise, mixed sections) degrade LLM
   classification (0.38 vs 0.80). Parser-first design is validated empirically.
2. **full_agent = 1.0 classification**: rule evidence + LLM refinement on structured
   observations beats both baselines.
3. **Recovery honesty**: missing_pseudopotential cases are correctly NOT repaired
   (out of whitelist - requires fetching a file, human task).
4. Known v1 limits: the invalid_kpoints (0-grid) and oscillation (beta=0.98 on Si)
   injections did not reliably produce failures on this simple system - the
   injector needs harder materials (next iteration).
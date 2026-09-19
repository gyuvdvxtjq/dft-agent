"""DFT-Agent CLI: init / run / diagnose / resume / benchmark."""

from __future__ import annotations

from pathlib import Path

import json

import typer
from rich.console import Console

app = typer.Typer(help="DFT-Agent: autonomous Quantum ESPRESSO calculation agent")
console = Console()


@app.command()
def init(
    structure: Path = typer.Argument(..., exists=True, help="CIF/pw.x input structure file"),
    task: str = typer.Option("relax", "--task", help="scf | relax | vc-relax"),
    output: Path = typer.Option("./runs/run", "--output", help="Run directory"),
):
    """Create a new DFT-Agent job from a structure file."""
    output.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]Created job skeleton at[/green] {output}")
    console.print(f"  structure : {structure}")
    console.print(f"  task      : {task}")
    console.print("[yellow]Note:[/yellow] agent loop lands in phase 2.")


@app.command()
def run(
    job_dir: Path = typer.Argument(..., help="Job directory created by init"),
    goal: str = typer.Option("Complete the calculation", "--goal"),
    max_retries: int = typer.Option(2, "--max-retries"),
):
    """Run the agent loop on a prepared job."""
    from dft_agent.agent import run_agent
    state = run_agent(str(job_dir), goal, max_attempts=max_retries)
    console.print(f"[bold]{state['status']}[/bold] {state['final_summary']}")


@app.command()
def diagnose(
    job_dir: Path = typer.Argument(..., help="Directory of a failed calculation"),
):
    """Diagnose an existing failed QE job directory."""
    from dft_agent.tools import qe_tools
    outs = sorted(Path(job_dir).glob("*.out"))
    if not outs:
        console.print("[red]no .out files found[/red]"); raise typer.Exit(1)
    obs = qe_tools.observe_log(str(outs[-1]))
    console.print_json(json.dumps(obs, ensure_ascii=False, indent=1))


@app.command()
def resume(run_id: str = typer.Argument(...)):
    """Resume an interrupted agent run from persisted state."""
    console.print(f"Resuming {run_id}")
    raise typer.Exit(code=2)  # phase 2


@app.command()
def benchmark(
    out_root: Path = typer.Option("./benchmarks/run1", "--out", help="Output directory"),
    systems: str = typer.Option("rules,llm_direct", "--systems"),
):
    """Run the evaluation suite (injected fault cases x systems)."""
    from dft_agent.benchmark.run_bench import run_benchmark
    res = run_benchmark(str(out_root), systems=systems.split(","))
    console.print_json(json.dumps(res["summary"]))


if __name__ == "__main__":
    app()

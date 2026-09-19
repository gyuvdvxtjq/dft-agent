"""DFT-Agent CLI: init / run / diagnose / resume / benchmark."""

from __future__ import annotations

from pathlib import Path

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
    console.print(f"[green]Agent loop starting for[/green] {job_dir}")
    console.print(f"  goal        : {goal}")
    console.print(f"  max retries : {max_retries}")
    raise typer.Exit(code=2)  # phase 2


@app.command()
def diagnose(
    job_dir: Path = typer.Argument(..., help="Directory of a failed calculation"),
):
    """Diagnose an existing failed QE job directory."""
    console.print(f"[green]Diagnosing[/green] {job_dir}")
    raise typer.Exit(code=2)  # phase 2


@app.command()
def resume(run_id: str = typer.Argument(...)):
    """Resume an interrupted agent run from persisted state."""
    console.print(f"Resuming {run_id}")
    raise typer.Exit(code=2)  # phase 2


@app.command()
def benchmark(bench_dir: Path = typer.Argument(..., help="Benchmark case directory")):
    """Run the evaluation suite."""
    console.print(f"Benchmark: {bench_dir}")
    raise typer.Exit(code=2)  # phase 4


if __name__ == "__main__":
    app()

import datetime
import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich import box
from rich.table import Table
from rich.text import Text

# Force UTF-8 output on Windows so Unicode renders correctly
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.environ.setdefault("PYTHONUTF8", "1")

console = Console(highlight=False)


def agent_say(message: str):
    """Agent speaks in persona — main output voice."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]{ts}[/dim] [bold magenta]* VoteWhisperer:[/bold magenta] {message}")


def action(label: str, detail: str = ""):
    """Show an action being executed."""
    detail_str = f" [dim]{detail}[/dim]" if detail else ""
    console.print(f"  [bold yellow]>>[/bold yellow] [yellow]{label}[/yellow]{detail_str}")


def ok(message: str):
    """Success result."""
    console.print(f"  [bold green][OK][/bold green] {message}")


def warn(message: str):
    """Warning."""
    console.print(f"  [bold yellow][!][/bold yellow]  [yellow]{message}[/yellow]")


def err(message: str):
    """Error."""
    console.print(f"  [bold red][ERR][/bold red] [red]{message}[/red]")


def info(message: str):
    """Neutral info line."""
    console.print(f"  [dim]-[/dim] {message}")


def divider():
    console.print("[dim]" + "-" * 62 + "[/dim]")


def panel(title: str, content: str, style: str = "blue"):
    console.print(Panel(content, title=f"[bold]{title}[/bold]", border_style=style, box=box.ASCII))


def song_table(songs: list[dict]):
    """Render a ranked song table."""
    table = Table(
        title="🏆 VoteWhisperer Prediction Board",
        box=box.ASCII,
        show_lines=True,
        border_style="magenta",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Song", style="bold cyan", min_width=24)
    table.add_column("Score", justify="right", style="bold yellow", width=7)
    table.add_column("Confidence", justify="center", width=12)
    table.add_column("Signals", style="dim", min_width=28)

    for i, s in enumerate(songs, 1):
        score = s.get("score", 0)
        conf_pct = f"{score * 100:.0f}%"
        bar_len = int(score * 10)
        bar = "[green]" + "█" * bar_len + "[/green]" + "[dim]" + "░" * (10 - bar_len) + "[/dim]"
        table.add_row(
            str(i),
            s.get("name", "Unknown"),
            f"{score:.3f}",
            bar,
            s.get("signal_summary", ""),
        )
    console.print(table)


def mock_badge():
    """Show a visible MOCK MODE banner."""
    console.print(
        Panel(
            "[bold yellow]MOCK MODE ON[/bold yellow] — no real txs or API calls. "
            "Set [cyan]MOCK_MODE=false[/cyan] in .env to go live.",
            border_style="yellow",
            box=box.ASCII,
        )
    )

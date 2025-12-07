import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.table import Table

from . import db
from .process_manager import (
    BotNotFoundError,
    get_bot_status,
    start_bot,
    stop_bot,
)

app = typer.Typer()
console = Console()

BASE_DIR = Path(__file__).resolve().parent.parent
BOTS_ROOT = BASE_DIR / "bots"


def _ensure_bots_root() -> Path:
    BOTS_ROOT.mkdir(parents=True, exist_ok=True)
    return BOTS_ROOT


def _print_discord_setup_help() -> None:
    console.print()
    console.rule("Next steps in Discord Developer Portal")
    console.print(
        "- Use the bot token from the Bot tab (not the public key or client ID)."
    )
    console.print(
        "- Under Privileged Gateway Intents, enable only what your bot actually needs "
        "(typically: Message Content, and optionally Server Members / Presence)."
    )
    console.print("- When generating the invite link (OAuth2 -> URL Generator):")
    console.print(
        "  * Scopes: bot (and applications.commands if you use slash commands)."
    )
    console.print(
        "  * Start with minimal Bot Permissions: View Channels, Read Message History, "
        "Send Messages, Embed Links, Attach Files, Add Reactions."
    )
    console.print(
        "  * Only grant stronger permissions (Manage Messages, Kick/Ban Members, "
        "Manage Roles, Administrator) if the bot code actually needs them."
    )
    console.print()


@app.command("list")
def list_bots() -> None:
    rows = db.list_bots()
    if not rows:
        console.print("No bots registered.")
        return

    table = Table(title="Registered bots")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Name", style="bold")
    table.add_column("Status")
    table.add_column("PID")
    table.add_column("Repo")
    table.add_column("Local path")

    for row in rows:
        pid = row["process_pid"]
        table.add_row(
            str(row["id"]),
            row["name"],
            row["status"],
            str(pid) if pid is not None else "-",
            row["repo_url"] or "-",
            row["local_path"],
        )

    console.print(table)


@app.command("add-local")
def add_local(
    name: str = typer.Argument(..., help="Logical name for this bot"),
    path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    entrypoint: str = typer.Option("main.py", help="Python file to run inside the bot folder"),
    token: str = typer.Option(..., prompt=True, hide_input=True, help="Discord bot token"),
    db_uri: Optional[str] = typer.Option(None, help="Database URI or path used by this bot"),
    invite_url: Optional[str] = typer.Option(
        None,
        help="Optional stored Discord invite URL for this bot",
    ),
) -> None:
    local_path = path.resolve()
    if invite_url is None:
        _print_discord_setup_help()
        raw = console.input(
            "Optional: paste the Discord invite URL for this bot (or leave blank): "
        )
        invite_url = raw.strip() or None
    bot_id = db.create_bot(
        name=name,
        repo_url=None,
        local_path=str(local_path),
        entrypoint=entrypoint,
        discord_token=token,
        db_uri=db_uri,
        invite_url=invite_url,
    )
    console.print(f"Registered bot {name!r} with id {bot_id}")


@app.command("ingest-github")
def ingest_github(
    repo_url: str = typer.Argument(..., help="GitHub repository URL"),
    name: Optional[str] = typer.Option(None, help="Optional logical name; defaults to repo name"),
    entrypoint: str = typer.Option("main.py", help="Python file to run inside the cloned repo"),
    token: str = typer.Option(..., prompt=True, hide_input=True, help="Discord bot token"),
    db_uri: Optional[str] = typer.Option(None, help="Database URI or path used by this bot"),
    branch: Optional[str] = typer.Option(None, help="Branch to clone"),
    invite_url: Optional[str] = typer.Option(
        None,
        help="Optional stored Discord invite URL for this bot",
    ),
) -> None:
    root = _ensure_bots_root()

    parsed = urlparse(repo_url)
    repo_name = Path(parsed.path).stem or "bot"
    if not name:
        name = repo_name

    target_dir = root / name
    if target_dir.exists():
        console.print(f"Target folder already exists: {target_dir}")
        raise typer.Exit(code=1)

    clone_cmd = ["git", "clone"]
    if branch:
        clone_cmd.extend(["-b", branch])
    clone_cmd.extend([repo_url, str(target_dir)])

    console.print(f"Cloning {repo_url} into {target_dir}...")
    try:
        subprocess.run(clone_cmd, check=True)
    except FileNotFoundError:
        console.print("git executable not found. Install git on this machine.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as exc:
        console.print(f"git clone failed with exit code {exc.returncode}")
        raise typer.Exit(code=1)

    if invite_url is None:
        _print_discord_setup_help()
        raw = console.input(
            "Optional: paste the Discord invite URL for this bot (or leave blank): "
        )
        invite_url = raw.strip() or None

    bot_id = db.create_bot(
        name=name,
        repo_url=repo_url,
        local_path=str(target_dir.resolve()),
        entrypoint=entrypoint,
        discord_token=token,
        db_uri=db_uri,
        invite_url=invite_url,
    )
    console.print(f"Ingested bot {name!r} from {repo_url} with id {bot_id}")


@app.command("start")
def start_command(
    identifier: str = typer.Argument(..., help="Bot id or name"),
) -> None:
    try:
        pid = start_bot(identifier)
    except BotNotFoundError as exc:
        console.print(str(exc))
        raise typer.Exit(code=1)
    console.print(f"Started bot {identifier!r} with PID {pid}")


@app.command("stop")
def stop_command(
    identifier: str = typer.Argument(..., help="Bot id or name"),
    force: bool = typer.Option(False, help="Force kill the process"),
) -> None:
    try:
        stop_bot(identifier, force=force)
    except BotNotFoundError as exc:
        console.print(str(exc))
        raise typer.Exit(code=1)
    console.print(f"Stopped bot {identifier!r}")


@app.command("status")
def status_command(
    identifier: str = typer.Argument(..., help="Bot id or name"),
) -> None:
    try:
        status = get_bot_status(identifier)
    except BotNotFoundError as exc:
        console.print(str(exc))
        raise typer.Exit(code=1)
    console.print(f"Status for {identifier!r}: {status}")


@app.command("info")
def info_command(
    identifier: str = typer.Argument(..., help="Bot id or name"),
) -> None:
    row = None
    if identifier.isdigit():
        row = db.get_bot_by_id(int(identifier))
    if row is None:
        row = db.get_bot_by_name(identifier)
    if row is None:
        console.print(f"Bot not found: {identifier}")
        raise typer.Exit(code=1)

    table = Table(title=f"Bot {row['name']} details")
    table.add_column("Field")
    table.add_column("Value")

    for field in [
        "id",
        "name",
        "status",
        "process_pid",
        "repo_url",
        "invite_url",
        "local_path",
        "entrypoint",
        "db_uri",
        "created_at",
        "updated_at",
    ]:
        table.add_row(field, str(row[field]))

    console.print(table)

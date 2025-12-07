import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .db import (
    get_bot_by_id,
    get_bot_by_name,
    update_bot_status_and_pid,
)


BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_ROOT = BASE_DIR / "logs"


class BotNotFoundError(Exception):
    pass


def _get_bot(identifier: str):
    row = None
    if identifier.isdigit():
        row = get_bot_by_id(int(identifier))
    if row is None:
        row = get_bot_by_name(identifier)
    if row is None:
        raise BotNotFoundError(f"Bot not found: {identifier}")
    return row


def is_process_running(pid: Optional[int]) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def start_bot(identifier: str) -> int:
    row = _get_bot(identifier)
    bot_id = int(row["id"])
    pid = row["process_pid"]
    if is_process_running(pid):
        update_bot_status_and_pid(bot_id, "running", pid)
        return int(pid)

    local_path = Path(row["local_path"])
    entrypoint = Path(row["entrypoint"])
    if not entrypoint.is_absolute():
        entrypoint = local_path / entrypoint

    if not entrypoint.exists():
        raise RuntimeError(f"Entrypoint does not exist: {entrypoint}")

    env = os.environ.copy()
    env["DISCORD_TOKEN"] = row["discord_token"]
    db_uri = row["db_uri"]
    if db_uri:
        env["BOT_DB_URI"] = db_uri

    LOGS_ROOT.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_ROOT / f"bot_{bot_id}_{row['name']}.log"
    log_handle = open(log_file, "a", encoding="utf-8")

    proc = subprocess.Popen(
        [sys.executable, str(entrypoint)],
        cwd=str(local_path),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )

    log_handle.close()

    update_bot_status_and_pid(bot_id, "running", proc.pid)
    return int(proc.pid)


def stop_bot(identifier: str, force: bool = False) -> None:
    row = _get_bot(identifier)
    bot_id = int(row["id"])
    pid = row["process_pid"]
    if not is_process_running(pid):
        update_bot_status_and_pid(bot_id, "stopped", None)
        return

    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        except Exception:
            pass
    else:
        sig = signal.SIGKILL if force else signal.SIGTERM
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass

    update_bot_status_and_pid(bot_id, "stopped", None)


def get_bot_status(identifier: str) -> str:
    row = _get_bot(identifier)
    bot_id = int(row["id"])
    pid = row["process_pid"]
    status = row["status"]

    if is_process_running(pid):
        if status != "running":
            update_bot_status_and_pid(bot_id, "running", pid)
        return "running"

    if status != "stopped" or pid is not None:
        update_bot_status_and_pid(bot_id, "stopped", None)
    return "stopped"

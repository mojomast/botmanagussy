# botmanagussy

> **Experimental, in-development multi-Discord-bot manager. Do not treat as production ready. APIs, CLI commands, and internals may change frequently.**

botmanagussy is a CLI-first manager for running and supervising multiple Discord bots on a single VPS. It focuses on:

- **Managing many bots** from one place.
- **Ingesting bots from GitHub repos** into a managed `bots/` folder.
- **Starting/stopping bots as separate processes** with environment variables for tokens and DB URIs.
- **Tracking metadata** like repo URL, local path, entrypoint, and per-bot database connection.

A web dashboard can be layered on top later, but the core is a simple, scriptable CLI you can run on a Debian VPS.

---

## Features (current)

- **CLI-based manager** built with Typer + Rich.
- **SQLite-backed registry** (file: `manager.db`) storing:
  - Bot name and ID.
  - GitHub repo URL (if ingested).
  - Local path and entrypoint.
  - Discord token (currently stored in plain text – experimental, see **Security**).
  - Per-bot DB URI (e.g. SQLite file path or Postgres connection string).
  - Status (`running` / `stopped`) and process PID.
- **GitHub ingestion**:
  - `ingest-github` clones a repo and registers it as a managed bot.
- **Local bot registration**:
  - `add-local` registers a bot that already exists on disk.
- **Process management**:
  - `start`, `stop`, `status`, and `info` for each bot.
- **Env-based configuration for bots**:
  - `DISCORD_TOKEN` and `BOT_DB_URI` are injected as env vars when a bot is started.

This project is deliberately minimal and opinionated; it is meant as a playground for experimenting with multi-bot orchestration, LLM tool integrations, and future two-way communication between bots and the manager.

---

## How it’s built

- **Language**: Python (3.10+ recommended).
- **Core libraries** (see `requirements.txt`):
  - `typer[all]` – for the CLI.
  - `rich` – for pretty terminal output.
  - `sqlite3` (standard library) – for the manager database.
  - `aiosqlite`, `discord.py`, `aiohttp`, `python-dotenv` – included for compatibility with typical Discord bots and async DB usage.
  - `gitpython`, `cryptography` – reserved for future enhancements (e.g. token encryption, advanced Git workflows).
- **Data store**: SQLite file `manager.db` in the project root.
  - Single table `bots` with columns such as `id`, `name`, `repo_url`, `local_path`, `entrypoint`, `discord_token`, `db_uri`, `status`, `process_pid`, timestamps.
- **Process supervision**:
  - Uses `subprocess.Popen` to start each bot as its own Python process.
  - The bot’s working directory is set to its repo folder.
  - Environment variables are injected before launch.
- **Structure**:
  - `botmanager/` – Python package containing:
    - `cli.py` – Typer app with all CLI commands.
    - `db.py` – SQLite helpers and schema initialization.
    - `process_manager.py` – logic to start/stop/check bot processes.
    - `__main__.py` – entrypoint for `python -m botmanager`.
  - `bots/` – created on demand; where GitHub-ingested bots are cloned.

The manager itself is *not* a Discord bot. It’s a controller process that runs alongside your bots and orchestrates them.

---

## Installation

Clone the repository and install dependencies into a virtual environment.

```bash
# Clone (example URL; adjust to your GitHub username/namespace)
git clone git@github.com:YOUR_USER/botmanagussy.git
cd botmanagussy

# Create and activate a virtual environment (Debian / Linux)
python3 -m venv .venv
source .venv/bin/activate

# On Windows:
# python -m venv .venv
# .venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt
```

Requirements:

- Python 3.10+.
- `git` installed (for `ingest-github`).
- A Debian-like environment is assumed for server deployment, but the code should run on other OSes with minor adjustments.

---

## Usage overview

All commands are available via the module entrypoint:

```bash
python -m botmanager --help
```

### List bots

```bash
python -m botmanager list
```

Shows a table of all registered bots with ID, name, status, PID, repo URL, and local path.

### Register an existing local bot

Use this when you already have a bot cloned on disk:

```bash
python -m botmanager add-local \
  "my-bot" \
  ./path/to/my_bot_repo \
  --entrypoint main.py \
  --db-uri sqlite:///my_bot.db
```

You will be prompted (hidden) for the Discord bot token.

Fields:

- **name** – logical name used by the manager (can differ from repo folder name).
- **path** – existing directory containing your bot.
- **entrypoint** – Python file inside that directory that should be executed (default: `main.py`).
- **db-uri** – optional; connection string or path to the bot’s own database.

### Ingest a bot from GitHub

Use this when you want the manager to clone a repo into its own `bots/` folder and manage it from there:

```bash
python -m botmanager ingest-github \
  https://github.com/YOUR_USER/your-bot-repo.git \
  --name chat-bot \
  --entrypoint main.py \
  --db-uri sqlite:///chat_bot.db
```

Notes:

- If `--name` is omitted, the name defaults to the repo name.
- The repo is cloned into `bots/<name>` relative to the project root.
- You will be prompted (hidden) for the Discord bot token.

### Start a bot

```bash
python -m botmanager start chat-bot
# or by ID:
python -m botmanager start 1
```

This will:

- Spawn a new Python process with `python <entrypoint>`.
- Set the working directory to the bot’s folder.
- Inject environment variables:
  - `DISCORD_TOKEN` – the stored Discord bot token.
  - `BOT_DB_URI` – the stored DB URI (if configured).

### Stop a bot

```bash
python -m botmanager stop chat-bot
# Force kill if needed (SIGKILL on Linux):
python -m botmanager stop chat-bot --force
```

### Check status

```bash
python -m botmanager status chat-bot
```

This checks whether the stored PID is actually alive and updates the stored status accordingly.

### Inspect bot details

```bash
python -m botmanager info chat-bot
# or
python -m botmanager info 1
```

Prints detailed metadata for a bot: ID, name, status, PID, repo URL, local path, entrypoint, DB URI, and timestamps.

---

## Expectations for managed bots

To work smoothly with botmanagussy, each managed bot should:

1. **Be a Python Discord bot** (e.g. using `discord.py`).
2. **Read configuration from environment variables**, especially:

   ```python
   import os

   DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]  # required
   BOT_DB_URI = os.environ.get("BOT_DB_URI")     # optional
   ```

3. Use `DISCORD_TOKEN` when constructing the Discord client / bot.
4. Use `BOT_DB_URI` to connect to its own database (SQLite file, Postgres URI, etc.).

This keeps secrets and DB configuration in one place (the manager) and avoids scattering tokens across many `.env` files.

---

## Per-bot databases

Each bot can have its own database connection string stored as `db_uri` in the manager’s SQLite DB.

- The manager does **not** currently introspect or migrate these databases.
- Instead, it injects `BOT_DB_URI` into the bot’s environment when the process starts.
- You are free to use any DB backend and migration strategy inside the bot code itself.

Future ideas (not implemented yet):

- Helper commands like `db-shell`, `db-backup`, or `db-migrate` that operate on a bot’s DB using its `db_uri`.

---

## Experimental LLM/tool integrations (future direction)

botmanagussy is designed with LLM-driven bots in mind, where bots:

- Make API calls to LLMs.
- Expose a **tool schema** that allows the LLM to call arbitrary tools.

A future extension is to expose the bot manager itself as a **tool** that bots can call, enabling scenarios like:

- A bot asking the manager for information about other bots (`list_bots`, `status`).
- A bot requesting a soft restart of itself or a sibling bot.

This likely will involve:

- Adding a small HTTP API (e.g. FastAPI or aiohttp) on top of the existing process manager.
- Defining JSON tool schemas that your LLMs can call.

These features are **not implemented yet** and the design is subject to change.

---

## Security notes

This project is **experimental** and **not hardened for production**:

- Discord tokens are currently stored in plain text in the SQLite DB.
- There is no authentication/authorization layer.
- Process supervision is minimal and does not yet include robust monitoring or auto-restarts.

If you use this on a real VPS:

- Restrict access to the server and the `manager.db` file.
- Prefer running the manager under a non-root user.
- Consider using OS-level tools (like `systemd`) to keep the manager itself running.
- Plan to rotate tokens if you suspect compromise.

A future version may use the `cryptography` library to encrypt tokens at rest.

---

## Development & contributions

This repository is an evolving experiment. Expect breaking changes, refactors, and new commands as the design matures.

If you are hacking on botmanagussy yourself:

- Keep the CLI small and composable.
- Prefer explicit, scriptable commands over hidden magic.
- Treat the README and code comments as living documentation.

Have fun managing too many bots at once.

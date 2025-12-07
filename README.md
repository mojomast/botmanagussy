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
 - **Per-bot logging**:
   - Each bot's stdout/stderr is written to `logs/bot_<id>_<name>.log`.
 - **Git pull updates**:
   - `pull` can run `git pull` inside a bot's repo (with optional restart).
 - **Optional invite URL tracking**:
   - You can store the Discord invite URL alongside each bot for reference.

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
  - Single table `bots` with columns such as `id`, `name`, `repo_url`, `local_path`, `entrypoint`, `discord_token`, `db_uri`, `invite_url`, `status`, `process_pid`, timestamps.
- **Process supervision**:
  - Uses `subprocess.Popen` to start each bot as its own Python process.
  - The bot’s working directory is set to its repo folder.
  - Environment variables are injected before launch.
  - Each bot's output is streamed to a per-bot log file under `logs/`.
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

### View logs for a bot

```bash
python -m botmanager logs chat-bot
python -m botmanager logs chat-bot --lines 100
```

This prints the tail of the per-bot log file under `logs/` (by default, the last 50 lines; configurable with `--lines`).

### Diagnose common issues

```bash
python -m botmanager diagnose chat-bot
python -m botmanager diagnose chat-bot --lines 150
```

`diagnose` shows recent log lines and performs simple pattern-based checks. For example, if it detects `discord.errors.PrivilegedIntentsRequired`, it will explain that the bot is requesting privileged gateway intents (Message Content, Server Members, Presence) that are not enabled in the Discord Developer Portal, and point you to the Bot tab to toggle them on.

### Fix an incorrect entrypoint

If you registered a bot with the wrong entrypoint, you can fix it without touching the database:

```bash
python -m botmanager set-entrypoint chat-bot main.py
# or, for a nested entrypoint:
python -m botmanager set-entrypoint chat-bot src/bot.py
```

The manager will update the stored `entrypoint` for that bot. It will warn if the path you provide does not currently exist on disk.

### Rotate a bot's Discord token

If a bot's Discord token changes (for example, you reset it in the Developer Portal), you can update the stored token without re-adding the bot:

```bash
python -m botmanager set-token chat-bot
python -m botmanager set-token 1
```

You will be prompted (hidden, with confirmation) for the new token. After updating, restart the bot so the new token takes effect.

### Interactive TUI-style menu

If you prefer not to remember individual commands, you can launch a simple text-based menu:

```bash
python -m botmanager menu
```

From there you can:

- List bots.
- Start/stop bots.
- Check status.
- View logs.
- Run diagnostics.
- Pull latest code for a bot (with optional restart).
- Update a bot's Discord token.

### Update a bot from its GitHub repo

For bots that were ingested from GitHub (i.e. have a `repo_url` and a `.git` directory):

```bash
python -m botmanager pull chat-bot

# Use --rebase if you prefer rebasing local changes
python -m botmanager pull chat-bot --rebase

# If the bot is running, stop it, pull, and restart it
python -m botmanager pull chat-bot --restart
```

`pull` will:

- Look up the bot by id or name.
- Ensure there is a recorded `repo_url` and a `.git` directory at `local_path`.
- Stop the bot if it is currently running.
- Run `git pull` (or `git pull --rebase` if requested) in the bot's repo.
- Optionally restart the bot if `--restart` is set and it was previously running.

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

Bots should also read any additional API keys they need (LLMs, tools, etc.) from environment variables, for example:

```python
REQUESTY_API_KEY = os.environ.get("REQUESTY_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
```

---

## Per-bot databases

Each bot can have its own database connection string stored as `db_uri` in the manager’s SQLite DB.

- The manager does **not** currently introspect or migrate these databases.
- Instead, it injects `BOT_DB_URI` into the bot’s environment when the process starts.
- You are free to use any DB backend and migration strategy inside the bot code itself.

Future ideas (not implemented yet):

- Helper commands like `db-shell`, `db-backup`, or `db-migrate` that operate on a bot’s DB using its `db_uri`.

---

## Environment and API keys

When you run `python -m botmanager`, botmanagussy will load environment variables from a `.env` file in the project root (using `python-dotenv`), and then propagate its environment to all bot processes.

This means you can define API keys and shared configuration once at the manager level, for example in `.env`:

```env
# Example .env
REQUESTY_API_KEY=your-requesty-key
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
```

and inside each bot, simply read them with `os.environ` or `os.getenv`.

You can also define per-bot keys using naming conventions, e.g. `DMUSSY_OPENAI_API_KEY`, and only the corresponding bot will use that variable in its code.

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

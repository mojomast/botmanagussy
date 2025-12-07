from pathlib import Path

from dotenv import load_dotenv

from .cli import app


BASE_DIR = Path(__file__).resolve().parent.parent


def main() -> None:
    # Load environment variables from a .env file in the project root so that
    # API keys and other settings are available to the manager and all bots.
    load_dotenv(BASE_DIR / ".env")
    app()


if __name__ == "__main__":
    main()

import subprocess
import sys

APP_FILE = "app.py"
VALID_CHOICES = {"cli", "ui"}


def _prompt_choice() -> str:
    """Ask the user whether to launch the web UI or the CLI."""
    print("How do you want to run Job Preparation Multiagent AI?")
    print("  [1] Web UI (Streamlit)  [default]")
    print("  [2] CLI")
    answer = input("Choose 1 or 2: ").strip()
    return "cli" if answer == "2" else "ui"


def _launch_ui() -> int:
    """Launch the Streamlit UI in this terminal."""
    print("Launching web UI (Streamlit)...")
    return subprocess.run(
        [sys.executable, "-m", "streamlit", "run", APP_FILE]
    ).returncode


def _launch_cli() -> None:
    from main import run_cli

    run_cli()


def main() -> None:
    choice = sys.argv[1].lower() if len(sys.argv) > 1 else _prompt_choice()
    if choice not in VALID_CHOICES:
        print(f"Unknown option {choice!r}. Use 'cli' or 'ui'.")
        raise SystemExit(2)

    if choice == "cli":
        _launch_cli()
    else:
        raise SystemExit(_launch_ui())


if __name__ == "__main__":
    main()

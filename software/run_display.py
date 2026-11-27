"""Start the SPECULA-1 preliminary live display (simulated data only).

From the repository root:
    .venv\\Scripts\\python.exe software/run_display.py
"""

import argparse
import sys
import webbrowser

from radar_display.engine import Engine
from radar_display.server import HOST, make_server
from radar_display.simulated import SimulatedSource


def keep_window_open() -> None:
    """A double-clicked .exe closes its window on exit, hiding any message."""
    if getattr(sys, "frozen", False):
        try:
            input("Press Enter to close this window.")
        except (EOFError, KeyboardInterrupt, OSError, RuntimeError):
            pass  # no keyboard attached


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="do not open it")
    args = parser.parse_args()

    engine = Engine(SimulatedSource())
    try:
        server = make_server(engine, args.port)
    except (OSError, OverflowError) as error:
        print(
            f"Cannot use port {args.port}: {error}\n"
            "Is the display already running? Close it, or start with --port 8766"
        )
        keep_window_open()
        return 1
    engine.start()
    url = f"http://{HOST}:{server.server_address[1]}/"
    print(
        f"SPECULA-1 display (SIMULATED data) at {url}\nPress Ctrl+C to stop.",
        flush=True,
    )
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        engine.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

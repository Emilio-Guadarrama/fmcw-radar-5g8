"""Build software/dist/specula-display.exe (Windows) with PyInstaller.

From the repository root:
    .venv\\Scripts\\python.exe software/build_exe.py
"""

import tempfile
from pathlib import Path

import PyInstaller.__main__

SOFTWARE = Path(__file__).resolve().parent
SIM = SOFTWARE.parent / "sim"
WEB = SOFTWARE / "radar_display" / "web"
DIST = SOFTWARE / "dist"
NAME = "specula-display"


def main() -> None:
    DIST.mkdir(exist_ok=True)
    # Ignore everything in dist/, this file included, so a build is not committed.
    (DIST / ".gitignore").write_text("*\n", encoding="utf-8")
    # PyInstaller's working files are not worth keeping.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        PyInstaller.__main__.run(
            [
                str(SOFTWARE / "run_display.py"),
                "--onefile",
                "--console",
                "--noconfirm",
                f"--name={NAME}",
                f"--paths={SOFTWARE}",
                f"--paths={SIM}",
                f"--add-data={WEB}:radar_display/web",
                f"--distpath={DIST}",
                f"--workpath={work}",
                f"--specpath={work}",
            ]
        )
    print(f"Built {DIST / (NAME + '.exe')}")


if __name__ == "__main__":
    main()

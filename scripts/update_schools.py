"""Refresh the school files the page reads. Home values are not touched.

Runs the CBE directory, Alberta contacts, and CBE zones. Each file is
replaced only when the new text differs. A source that fails or comes back
empty keeps the file already on disk. Grade 10–12 zones are included.

The page does not run this. Windows Task Scheduler does, weekly on Sunday
at 09:00 local time, including after a missed start once the computer is on.

Run:  .venv/bin/python scripts/update_schools.py
      .venv/bin/python scripts/update_schools.py --install-task
"""
from __future__ import annotations

import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "raw" / "logs" / "update_schools.log"
TASK = "school-maps-school-update"


def _log(line: str) -> None:
    print(line)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def run_step(name: str, fn) -> bool:
    """Run one refresh. A failure keeps the existing file and does not stop the rest."""
    try:
        code = fn()
    except SystemExit as exc:
        _log(f"FAIL {name}: {exc}")
        return False
    except Exception as exc:  # noqa: BLE001 - one source must not abort the others
        _log(f"FAIL {name}: {exc}")
        _log(traceback.format_exc().rstrip())
        return False
    if code not in (None, 0):
        _log(f"FAIL {name}: exit {code}")
        return False
    _log(f"ok {name}")
    return True


def refresh() -> int:
    """Refresh the three school sources. Exit 1 when any step failed."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_zones import main as zones_main
    from fetch_ab_contacts import main as contacts_main
    from fetch_cbe_directory import main as directory_main

    _log(f"--- {datetime.now().isoformat(timespec='seconds')} ---")
    ok = [
        run_step("cbe directory", directory_main),
        run_step("alberta contacts", contacts_main),
        run_step("cbe zones", lambda: zones_main(refresh=True)),
    ]
    return 0 if all(ok) else 1


def install_task() -> int:
    """Register the weekly task for the current user. Exit 1 when Python is missing."""
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = ROOT / ".venv" / "bin" / "python"
    if not python.exists():
        print("FAIL no .venv python; create the virtualenv first", file=sys.stderr)
        return 1
    script = Path(__file__).resolve()
    command = f"""
$action = New-ScheduledTaskAction -Execute '{python}' -Argument '{script}' -WorkingDirectory '{ROOT}'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 9:00am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName '{TASK}' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Output 'scheduled {TASK}'
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def main() -> int:
    """CLI entry. `--install-task` registers the weekly job; otherwise refresh now."""
    if "--install-task" in sys.argv:
        return install_task()
    return refresh()


if __name__ == "__main__":
    sys.exit(main())

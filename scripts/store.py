"""Write a generated data file only when its text changed.

Does not download anything. An empty string leaves the current file in place
so a failed build cannot wipe a good one.
"""
from pathlib import Path


def write_if_changed(path: Path, text: str) -> str:
    """Replace `path` with `text` when the bytes differ.

    Returns "updated", "unchanged", or "skipped". Empty text is skipped.
    """
    if not text or not text.strip():
        print(f"skipped {path.name}: empty")
        return "skipped"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        print(f"unchanged {path.name}")
        return "unchanged"
    path.write_text(text, encoding="utf-8")
    print(f"updated {path.name}")
    return "updated"

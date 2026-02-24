"""Placeholder entrypoint for the D2RSO GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

APP_TITLE = "D2RSO"
WINDOW_SIZE = "480x320"


def build_root() -> tk.Tk:
    """Create the placeholder window and return the Tk root."""
    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry(WINDOW_SIZE)
    root.resizable(False, False)

    wrapper = ttk.Frame(root, padding=24)
    wrapper.pack(fill="both", expand=True)

    heading = ttk.Label(wrapper, text="D2RSO", font=("Segoe UI", 16, "bold"))
    heading.pack(pady=(0, 12))

    body = ttk.Label(
        wrapper,
        justify="center",
        text="Placeholder UI for D2RSO\nReplace with the real interface soon.",
    )
    body.pack()

    footer = ttk.Label(
        wrapper,
        foreground="#555555",
        text="Close this window to exit.",
    )
    footer.pack(pady=(12, 0))

    return root


def run() -> None:
    """Launch the placeholder GUI window."""
    try:
        root = build_root()
    except tk.TclError as exc:  # pragma: no cover - only triggered on missing display
        raise RuntimeError("Tkinter GUI could not be initialized") from exc

    root.mainloop()


if __name__ == "__main__":
    run()

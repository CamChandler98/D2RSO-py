"""Module entrypoint so `python -m d2rso` works."""

from __future__ import annotations


def run() -> None:
    if __package__:
        from .main import run as _run
    else:
        from d2rso.main import run as _run

    _run()


if __name__ == "__main__":
    run()

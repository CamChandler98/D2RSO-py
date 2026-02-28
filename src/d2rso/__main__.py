"""Module entrypoint so `python -m d2rso` works."""

from __future__ import annotations


def run() -> None:
    from .main import run as _run

    _run()


if __name__ == "__main__":
    run()

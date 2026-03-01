"""Print raw pygame joystick/controller events for local input debugging."""

from __future__ import annotations

import argparse
import time
from typing import Any


def _event_value(event: Any, name: str) -> Any:
    return getattr(event, name, None)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dump raw pygame joystick/controller events to stdout."
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=30.0,
        help="How long to listen before exiting. Use 0 to run until Ctrl+C.",
    )
    args = parser.parse_args()

    import pygame

    pygame.init()
    pygame.joystick.init()

    joysticks = []
    for index in range(max(0, int(pygame.joystick.get_count()))):
        joystick = pygame.joystick.Joystick(index)
        joystick.init()
        joysticks.append(joystick)
        print(
            f"joystick[{index}] name={joystick.get_name()!r} "
            f"buttons={joystick.get_numbuttons()} "
            f"axes={joystick.get_numaxes()} "
            f"hats={joystick.get_numhats()}"
        )

    if not joysticks:
        print("No joystick detected.")
        pygame.quit()
        return 1

    print("Listening for raw events...")
    started_at = time.monotonic()

    try:
        while True:
            for event in pygame.event.get():
                details = {
                    "button": _event_value(event, "button"),
                    "axis": _event_value(event, "axis"),
                    "value": _event_value(event, "value"),
                    "instance_id": _event_value(event, "instance_id"),
                    "joy": _event_value(event, "joy"),
                    "hat": _event_value(event, "hat"),
                }
                print(
                    f"{pygame.event.event_name(event.type)} "
                    + " ".join(f"{key}={value!r}" for key, value in details.items())
                )

            if args.seconds > 0 and time.monotonic() - started_at >= args.seconds:
                break

            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        for joystick in reversed(joysticks):
            try:
                joystick.quit()
            except Exception:
                pass
        pygame.quit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

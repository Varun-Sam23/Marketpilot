"""Compatibility entry point for MarketPilot's multi-agent report engine.

The canonical report pipeline lives in ``engine.py``. Keeping this module as a
thin wrapper prevents the scheduled runner and manual invocations from drifting
apart and guarantees they use the same specialist-agent orchestration path.
"""

from engine import run


if __name__ == "__main__":
    run()

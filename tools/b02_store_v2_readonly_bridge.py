#!/usr/bin/env python3
"""Bounded B02 V2 reader connection via the pre-existing Docker loopback.

Reuses the established B02 transport; no database credential, port mapping,
role grants, modified pg_hba, SQL write or new infrastructure. The store
emitter itself enforces PostgreSQL REPEATABLE READ, READ ONLY and current
session_user/current_user == solveris_b02_writer.
"""
from __future__ import annotations

import os
import sys

from tools import b02_g5_v5_local_bridge as bridge
from tools import b02_store_emission_v2_windows as emitter

EMITTER = "tools/b02_store_emission_v2_windows.py"
ENV = "SOLVERIS_B02_READER_DSN"
READER = "solveris_b02_writer"


def main():
    if os.environ.get(ENV):
        raise RuntimeError("STOP_B02_STORE_BRIDGE_MANUAL_DSN_ALREADY_SET")
    if (bridge.CONTAINER != "solveris-pg17-migration-test"
            or bridge.DATABASE != "solveris_b02_r4g_test"
            or bridge.ROLE != "solveris_b02_policy_writer"):
        raise RuntimeError("STOP_B02_STORE_BRIDGE_TARGET_CHANGED")
    bridge.validate_checkout(EMITTER)
    with bridge.managed_container():
        with bridge.loopback_transport() as port:
            # A process-local ephemeral URL. No secret is printed or persisted.
            os.environ[ENV] = (
                f"postgresql+psycopg2://{READER}@127.0.0.1:{port}/{bridge.DATABASE}"
                "?sslmode=disable&connect_timeout=8")
            try:
                emitter.main()
            finally:
                os.environ.pop(ENV, None)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc)[:450],file=sys.stderr)
        raise SystemExit(2) from None

"""Debug logger with a global toggle flag."""

import sys
from datetime import datetime
from typing import Any
import json

DEBUG: bool = False

def set_debug(flag: bool = True) -> None:
    global DEBUG
    DEBUG = bool(flag)

def debug(msg: str, *args: Any) -> None:
    if not DEBUG:
        return
    if args:
        try:
            msg = msg % args
        except Exception:
            msg = f"{msg} | args={args}"
    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}", file=sys.stderr, flush=True)


def debug_dump_ir_json(d) -> None:
    """Pretty-print the IR document as JSON"""
    if not DEBUG:
        return
    if d is None:
        print("[IR JSON] IR is None", file=sys.stderr)
        return
    try:
        print("[IR JSON]", file=sys.stderr)
        print(d.model_dump_json(indent=2), file=sys.stderr, flush=True)
    except Exception as e:
        debug("failed to dump IR json: %s", e)


def debug_dump_finding_json(f) -> None:
    """Pretty-print a single finding as JSON."""
    if not DEBUG:
        return
    elif f is None:
        print("[FINDING JSON] Finding is None", file=sys.stderr)
        return
    try:
        print("[FINDING JSON]", file=sys.stderr)
        print(f.model_dump_json(indent=2), file=sys.stderr, flush=True)
    except Exception as e:
        debug("failed to dump finding json: %s", e)

def dump_config_json(c) -> None:
    """Pretty-print a config object as JSON."""
    if not DEBUG:
        return
    elif c is None:
        print("[CONFIG JSON] Config is None", file=sys.stderr)
        return
    try:
        print("[CONFIG JSON]", file=sys.stderr)
        print(c.model_dump_json(indent=2), file=sys.stderr, flush=True)
    except Exception as e:
        debug("failed to dump config json: %s", e)

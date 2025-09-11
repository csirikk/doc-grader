from datetime import datetime
from typing import Any

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
    print(f"[{ts}] {msg}")

from pathlib import Path
import hashlib

_counters = {}

def next_id(prefix: str) -> str:
    """Return the next sequential id for the given prefix."""
    n = _counters.get(prefix, 0) + 1
    _counters[prefix] = n
    return f"{prefix}-{n}"

def doc_hash(path: str) -> str:
    with open(path, "rb") as f:
        return "sha256:" + hashlib.sha256(f.read()).hexdigest()

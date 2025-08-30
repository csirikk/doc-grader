_counters = {}

def next_id(prefix: str) -> str:
    """Return the next sequential id for the given prefix."""
    n = _counters.get(prefix, 0) + 1
    _counters[prefix] = n
    return f"{prefix}-{n}"

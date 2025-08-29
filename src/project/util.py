from typing import List, Any

# Generate unique id with a prefix
def next_id(blocks: List[Any], prefix: str) -> str:
    return f"{prefix}-{len(blocks)+1}"

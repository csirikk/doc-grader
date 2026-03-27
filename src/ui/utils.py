"""Shared judge-status metadata for UI modules."""

STATUS_COLOURS: dict[str, str] = {
    "not_to_be_judged": "blue",
    "to_be_judged": "orange",
    "judged_adjusted": "yellow",
    "judged_approved": "green",
    "judged_dismissed": "red",
}

ALL_STATUSES: list[str] = [
    "not_to_be_judged",
    "to_be_judged",
    "judged_adjusted",
    "judged_approved",
    "judged_dismissed",
]

FILTER_OPTIONS: list[str] = ["All", *ALL_STATUSES]

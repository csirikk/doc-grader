"""Shared status metadata for UI modules."""

STATUS_COLOURS: dict[str, str] = {
    "approved": "green",
    "dismissed": "red",
    "proposed": "orange",
}

ALL_STATUSES: list[str] = ["proposed", "approved", "dismissed"]

FILTER_OPTIONS: list[str] = ["All", *ALL_STATUSES]

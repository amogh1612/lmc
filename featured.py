"""Monthly featured figures: five random people, the same for everyone during a given month."""

import datetime
import json
import random
import re

from rag import JSON_KB_PATH

FEATURED_COUNT = 5
MIN_BIO_CHARS = 250  # skip short spouse-only entries so every card has a real story behind it


def _eligible_people(path: str = JSON_KB_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        people = json.load(f).get("people", [])
    return [p for p in people if p.get("occupations") and len(p.get("biography", "")) >= MIN_BIO_CHARS]


def _teaser(bio: str, occupations: list[str], limit: int = 140) -> str:
    """First real sentence of the biography, skipping the leading occupation label."""
    # split on sentence ends, but not after abbreviations like "Rev." or initials like "W. E. B."
    sentences = re.split(r"(?<!\bRev\.)(?<!\bDr\.)(?<!\bSt\.)(?<!\bJr\.)(?<!\bSr\.)(?<!\bMr\.)(?<!\bMrs\.)(?<!\b[A-Z]\.)(?<=[.!?])\s+(?=[A-Z\"])", bio)
    label = ", ".join(occupations) + "."
    for s in sentences:
        if s.strip() and s.strip() != label:
            return s if len(s) <= limit else s[: limit - 1].rsplit(" ", 1)[0] + "…"
    return ""


def monthly_featured(today: datetime.date | None = None, count: int = FEATURED_COUNT) -> list[dict]:
    """Pick `count` people with a seed of the current year and month, so picks change on the 1st."""
    today = today or datetime.date.today()
    people = sorted(_eligible_people(), key=lambda p: p["id"])
    rng = random.Random(f"south-view-featured-{today.year}-{today.month:02d}")
    picks = rng.sample(people, min(count, len(people)))
    return [
        {
            "name": p["full_name"],
            "death_year": p.get("death_year"),
            "occupations": p.get("occupations", []),
            "teaser": _teaser(p["biography"], p.get("occupations", [])),
        }
        for p in picks
    ]

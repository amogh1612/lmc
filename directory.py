"""People directory for the filter panel and the prominent-figures section."""

import json
import re

from rag import JSON_KB_PATH

# Occupation labels are free text, so group them by keyword into a short list of categories.
OCCUPATION_GROUPS = {
    "Religion & ministry": ["minister", "preacher", "priest", "bishop", "church", "missionary", "religious",
                            "theologian", "churchman", "temperance"],
    "Education & scholarship": ["educator", "teacher", "scholar", "librarian", "historian", "philosopher",
                                "economist", "student"],
    "Civil rights & politics": ["civil rights", "activist", "politician", "legislat", "councilman", "civic",
                                "community", "orator", "lawyer", "marshal", "political", "chief of the"],
    "Business & finance": ["business", "entrepreneur", "banker", "insurance", "realtist", "real estate",
                           "accountant", "owner", "caterer", "manager", "executive", "financial", "investor",
                           "bookkeeper", "cashier", "beauti", "beauty", "barber", "promoter", "philanthropist"],
    "Medicine & nursing": ["physician", "nurse", "surgeon", "pharmacist", "druggist", "dentist"],
    "Music & performing arts": ["music", "singer", "pianist", "composer", "vaudeville", "dancer", "actor",
                                "songwriter", "arranger", "band leader", "rapper", "model"],
    "Writing, journalism & visual arts": ["author", "poet", "journalist", "editor", "reporter", "artist",
                                          "painter", "sculptor", "printmaker", "photographer", "cinematographer",
                                          "designer", "architect"],
    "Sports": ["baseball", "basketball", "boxer", "player"],
    "Military": ["airman", "marine", "soldier"],
    "Funeral industry & South-View": ["mortuary", "mortician", "funeral", "undertaker", "sexton", "grave",
                                      "south-view"],
    "Trades & public service": ["carpenter", "builder", "contractor", "plasterer", "plumber", "shoemaker",
                                "postal", "postmaster", "mail", "porter", "railway", "laborer", "domestic",
                                "butler", "police", "customs", "cotton", "social worker", "worker", "fraternal",
                                "masonic", "clubwoman", "volunteer"],
}
OTHER_GROUP = "Other / not listed"


def occupation_groups(occupations: list[str]) -> list[str]:
    groups = []
    for occ in occupations:
        o = occ.lower()
        for group, keys in OCCUPATION_GROUPS.items():
            if any(k in o for k in keys) and group not in groups:
                groups.append(group)
    return groups or [OTHER_GROUP]


def _load(path: str = JSON_KB_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _teaser(bio: str, occupations: list[str], limit: int = 150) -> str:
    label = ", ".join(occupations) + "."
    text = bio[len(label):].strip() if occupations and bio.startswith(label) else bio
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def load_people(path: str = JSON_KB_PATH) -> list[dict]:
    """Every named person, with fields the filters need."""
    db = _load(path)
    prominent = {f.get("person_id"): f for f in db.get("prominent_figures", [])}
    people = []
    for p in db.get("people", []):
        name = p.get("full_name", "")
        if not name or "preceding entry" in name.lower():
            continue
        fig = prominent.get(p["id"])
        people.append({
            "id": p["id"],
            "name": name,
            "last_name": p.get("last_name") or name.split()[-1],
            "birth_year": p.get("birth_year") or (fig or {}).get("birth_year"),
            "death_year": p.get("death_year"),
            "era": p.get("era") or "Unknown",
            "occupations": p.get("occupations", []),
            "groups": occupation_groups(p.get("occupations", [])),
            "aka": p.get("also_known_as", []),
            "teaser": _teaser(p.get("biography", ""), p.get("occupations", [])),
            "prominent": fig is not None,
        })
    return sorted(people, key=lambda x: (x["last_name"].lower(), x["name"].lower()))


def load_prominent(path: str = JSON_KB_PATH) -> list[dict]:
    return _load(path).get("prominent_figures", [])


def filter_people(people: list[dict], name: str = "", groups: list[str] | None = None,
                  eras: list[str] | None = None, died: tuple[int, int] | None = None,
                  prominent_only: bool = False) -> list[dict]:
    terms = [t for t in re.split(r"\s+", name.lower().strip()) if t]
    out = []
    for p in people:
        hay = " ".join([p["name"], *p["aka"], *p["occupations"]]).lower()
        if terms and not all(t in hay for t in terms):
            continue
        if groups and not set(groups) & set(p["groups"]):
            continue
        if eras and p["era"] not in eras:
            continue
        if died and (p["death_year"] is None or not died[0] <= p["death_year"] <= died[1]):
            continue
        if prominent_only and not p["prominent"]:
            continue
        out.append(p)
    return out

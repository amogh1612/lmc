"""Merge researched prominent-figure profiles into the South-View database.

Usage: python tools/add_prominent_figures.py
Reads research_notes/profiles_*.json and rewrites southview_rag_database.json in place.
Safe to re-run: earlier merged data is replaced, not duplicated.
"""

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "southview_rag_database.json")
PROFILE_GLOB = os.path.join(ROOT, "research_notes", "profiles_*.json")
ADDED_TAG = "prominent_research"

# Display order for the Prominent figures tab.
ORDER = ["pf_king_sr", "pf_alberta_king", "pf_ad_king", "pf_aaron", "pf_bond", "pf_hamilton", "pf_turner",
         "pf_herndon", "pf_russell", "pf_jesse_hill", "pf_jw_dobbs", "pf_mattiwilda_dobbs"]


def era_for(year: int | None) -> str | None:
    if not year:
        return None
    if year < 1900:
        return "19th century"
    if year < 1954:
        return "Early 20th century"
    if year <= 1968:
        return "Civil Rights era"
    if year < 2000:
        return "Late 20th century"
    return "21st century"


def validate(fig: dict) -> list[str]:
    problems = []
    n = len(fig.get("sources", []))
    for key in ("id", "full_name", "lifespan", "tagline", "sections", "sources"):
        if not fig.get(key):
            problems.append(f"missing {key}")
    for s in fig.get("sources", []):
        if not s.get("url", "").startswith("http"):
            problems.append(f"source without URL: {s.get('title')}")
    for item in fig.get("sections", []) + fig.get("timeline", []):
        idx = item.get("sources", [])
        if not idx:
            problems.append(f"no sources on: {item.get('heading') or item.get('year')}")
        if any(not isinstance(i, int) or not 1 <= i <= n for i in idx):
            problems.append(f"bad source index on: {item.get('heading') or item.get('year')}")
    return problems


def main() -> None:
    with open(DB_PATH, encoding="utf-8") as f:
        db = json.load(f)

    figures = []
    for path in sorted(glob.glob(PROFILE_GLOB)):
        with open(path, encoding="utf-8") as f:
            figures.extend(json.load(f))
    if not figures:
        sys.exit("No profiles found in research_notes/profiles_*.json")

    bad = {fig.get("id"): validate(fig) for fig in figures}
    bad = {k: v for k, v in bad.items() if v}
    if bad:
        for k, v in bad.items():
            print(k, v)
        sys.exit("Fix the problems above before merging.")

    # Undo any earlier merge so re-running is idempotent.
    people = [p for p in db["people"] if p.get("added_by") != ADDED_TAG]
    for p in people:
        p.pop("prominent", None)
    by_id = {p["id"]: p for p in people}
    next_num = max(int(p["id"].split("_")[1]) for p in people) + 1

    for fig in figures:
        pid = fig.get("person_id")
        if pid and pid in by_id:
            person = by_id[pid]
            if person["full_name"] != fig["full_name"]:
                sys.exit(f"{fig['id']}: name {fig['full_name']!r} does not match {pid} {person['full_name']!r}")
            person["prominent"] = True
            person["birth_year"] = fig.get("birth_year")
            for aka in fig.get("also_known_as", []):
                person.setdefault("also_known_as", [])
                if aka not in person["also_known_as"] and aka != person["full_name"]:
                    person["also_known_as"].append(aka)
        else:
            # Not in the book: create a person record from the researched profile.
            pid = f"person_{next_num:04d}"
            next_num += 1
            fig["person_id"] = pid
            overview = " ".join(s["text"] for s in fig["sections"]
                                if s["heading"] in ("Early life and family", "Career and achievements"))
            person = {
                "id": pid,
                "type": "buried_person",
                "full_name": fig["full_name"],
                "last_name": fig["full_name"].split()[-1],
                "birth_year": fig.get("birth_year"),
                "death_year": fig.get("death_year"),
                "era": era_for(fig.get("death_year")),
                "occupations": fig.get("occupations", []),
                "affiliated_organizations": [],
                "also_known_as": fig.get("also_known_as", []),
                "biography": overview,
                "source": "Web research; see web_sources",
                "web_sources": fig["sources"],
                "prominent": True,
                "added_by": ADDED_TAG,
            }
            people.append(person)
            by_id[pid] = person

    rank = {k: i for i, k in enumerate(ORDER)}
    figures.sort(key=lambda f: (rank.get(f["id"], len(ORDER)), f["full_name"]))

    db["people"] = people
    db["prominent_figures"] = figures
    meta = db["database_meta"]
    meta["version"] = "2.2"
    meta["total_person_records"] = len(people)
    meta["prominent_figure_profiles"] = len(figures)
    meta["record_types"]["prominent_figure"] = (
        "In-depth researched profiles of notable residents, split into sections with per-section web sources")
    meta["v2_2_notes"] = (
        "Added researched profiles for prominent figures from encyclopedias, archives and news obituaries "
        "(see research_notes/). Each section cites its own sources by URL. People not in Henderson (2018) "
        "were added as new person records tagged added_by='prominent_research'.")

    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print(f"Merged {len(figures)} profiles; {len(people)} person records.")


if __name__ == "__main__":
    main()

"""Add new content to the South-View database through a simple text menu.

How to run it:    python add_content.py
For testing only: python add_content.py --file some_copy.json

This script only ever changes southview_rag_database.json (or the --file copy)
and the backups/ folder next to it. See ADD_CONTENT_README.md for the staff guide.
"""

from __future__ import annotations

import __future__ as future_flags
import argparse
import datetime
import difflib
import json
import os
import re
import shutil
import sys
import tempfile
import textwrap
import traceback
import types
import unicodedata

try:
    # Without this, a Mac terminal can't accept a typed or pasted line longer than about 1,024 characters.
    import readline  # noqa: F401
except ImportError:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(SCRIPT_DIR, "southview_rag_database.json")

# Same labels, in the same order, as the Era filter on the website (ERA_ORDER in streamlit_app.py).
ALLOWED_ERAS = ["19th century", "Early 20th century", "Civil Rights era",
                "Late 20th century", "21st century", "Unknown"]

STAFF_TAG = "staff_addition"
LONG_TEXT_LIMIT = 1200
MANY_CURLY_QUOTES = 4
MANY_LINES = 5
MAX_MATCHES_SHOWN = 25
# featured.py only picks people with an occupation and at least this much biography.
FEATURED_MIN_BIO = 250

OWN_WORDS = "Write this in your own words. Do not paste text from the book, from articles or from websites."

WELCOME = (
    "Welcome. This tool adds new content to the South-View history database, one step at a time. "
    "It will ask you some questions, show you exactly what it is about to change, and save nothing "
    "unless you type \"yes\". It makes a backup before every save and checks the database afterward. "
    "Type q at any question to leave."
)

MENU = """
What would you like to do?
1. Add a new section to a prominent figure's profile
2. Add a timeline event to a prominent figure
3. Add a new source link to a prominent figure
4. Add a new frequently asked question (FAQ)
5. Add a new person to the directory
6. Update the biography of an existing person
7. Check the database for problems (changes nothing)
q. Quit
"""

NEXT_STEPS = """
What to do next:
1. Upload/commit `southview_rag_database.json` to GitHub (ask the maintainer if you don't have access).
2. Ask the app owner to Reboot the app at share.streamlit.io.
3. Search for the person on the live site to confirm."""

# Where error details go. main() points this at the backups folder next to the database.
error_log_path = os.path.join(SCRIPT_DIR, "backups", "last_error.txt")


class QuitProgram(Exception):
    """The person typed q or quit."""


class GoBack(Exception):
    """The person left a question blank, so return to the menu."""


class FriendlyError(Exception):
    """A problem we can explain. The message is shown to the person as written."""


def log_error() -> None:
    """Keep the technical details of the current error for the maintainer."""
    try:
        os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n{traceback.format_exc()}")
    except OSError:
        pass  # never let trouble writing the log hide the original problem


# ---------------------------------------------------------------------------
# Tidying up text
# ---------------------------------------------------------------------------

SMART_CHARACTERS = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
})


def clean_text(text: str) -> str:
    """Straighten smart quotes, remove stray characters, and collapse extra spaces and line breaks."""
    text = text.encode("utf-8", "ignore").decode("utf-8").translate(SMART_CHARACTERS)
    text = re.sub(r"\s+", " ", text)  # also turns line breaks and non-breaking spaces into one space
    text = "".join(c for c in text if unicodedata.category(c) not in ("Cc", "Cf"))
    return text.strip()


def simplified(text: str) -> str:
    """Lowercase, accent-free text, for comparing names and questions."""
    text = unicodedata.normalize("NFKD", clean_text(text))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def wrapped(label: str, text: str) -> list[str]:
    """Format a label and a long value so the whole value is readable in the terminal."""
    return [f"  {label}:"] + textwrap.wrap(str(text), width=88, initial_indent="    ", subsequent_indent="    ")


def looks_pasted(raw: str) -> list[str]:
    """Reasons this text may have been copied. It must get the text as typed, before clean_text."""
    reasons = []
    if len(clean_text(raw)) > LONG_TEXT_LIMIT:
        reasons.append(f"it is over {LONG_TEXT_LIMIT:,} characters long")
    if len(re.findall("[‘’“”]", raw)) >= MANY_CURLY_QUOTES:
        reasons.append("it contains many curly quotation marks, which usually come from a book or website")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if re.search(r"\n\s*\n", raw.strip()) or len(lines) >= MANY_LINES:
        reasons.append("it has several paragraphs or line breaks, like a passage copied from somewhere")
    return reasons


# ---------------------------------------------------------------------------
# Asking questions
# ---------------------------------------------------------------------------

def discard_leftover_input() -> None:
    """Throw away lines left over from a multi-line paste, so they can't answer the next question."""
    try:
        if not sys.stdin.isatty():
            return
        if os.name == "nt":
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getwch()
        else:
            import termios
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass  # only a safety net, so failing here should never stop the person


def ask(prompt: str, discard_leftovers: bool = True) -> str:
    """Ask one question. Handles q, quit, Ctrl-C and a closed terminal the same way."""
    if discard_leftovers:
        discard_leftover_input()
    try:
        answer = input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        raise QuitProgram()
    if answer.strip().lower() in ("q", "quit"):
        raise QuitProgram()
    return answer


def ask_required(prompt: str) -> str:
    """Ask for a short answer. Leaving it blank goes back to the menu."""
    answer = clean_text(ask(f"{prompt} (leave blank to go back): "))
    if not answer:
        raise GoBack()
    return answer


def ask_yes(prompt: str) -> bool:
    return ask(f"{prompt} (yes/no): ").strip().lower() == "yes"


def read_several_lines(label: str) -> str:
    """Read text that may run over several lines. Ends at DONE, because a paste can contain blank lines."""
    print(f"{label}: type or paste it below. When you have finished, type DONE on a line of its own "
          "and press Enter. (Leave the first line blank to go back.)")
    lines = []
    while True:
        line = ask("> ", discard_leftovers=not lines)
        if not lines and not line.strip():
            raise GoBack()
        if line.strip().lower() == "done":
            if clean_text("\n".join(lines)):
                return "\n".join(lines)
            print("Nothing has been entered yet. Please type your text, then DONE.")
            continue
        lines.append(line)


def ask_own_words(label: str, long_text: bool = False) -> str:
    """Ask for text the person writes themselves, with the copyright reminder and paste warning."""
    while True:
        print(f"\n{OWN_WORDS}")
        raw = read_several_lines(label) if long_text else ask(f"{label} (leave blank to go back): ")
        if not clean_text(raw):
            raise GoBack()
        reasons = looks_pasted(raw)
        if reasons:
            print("\nPlease check this text: " + "; ".join(reasons) + ".")
            print("This project must not copy from the book, articles or websites.")
            if not ask_yes("Is this really in your own words, and do you want to keep it?"):
                print("Okay, that text was not kept. Please enter it again.")
                continue
        return clean_text(raw)


def ask_choice(prompt: str, count: int) -> int:
    """Ask for a number from 1 to count and return it. Blank goes back to the menu."""
    while True:
        answer = ask(f"{prompt} (1-{count}, leave blank to go back): ").strip()
        if not answer:
            raise GoBack()
        if answer.isdigit() and 1 <= int(answer) <= count:
            return int(answer)
        print(f"Please type a number from 1 to {count}.")


def ask_year(prompt: str, earliest: int = 1700):
    """Ask for an optional four-digit year. Returns a number, or None if left blank."""
    this_year = datetime.date.today().year
    while True:
        answer = clean_text(ask(f"{prompt} (leave blank if unknown): "))
        if not answer:
            return None
        if re.fullmatch(r"\d{4}", answer) and earliest <= int(answer) <= this_year:
            return int(answer)
        print(f"Please type a four-digit year from {earliest} to {this_year}, such as 1952, or leave it blank.")


def ask_list(prompt: str) -> list[str]:
    """Ask for a comma-separated list. Blank gives an empty list."""
    items = []
    for item in clean_text(ask(f"{prompt} (separate with commas, or leave blank if none): ")).split(","):
        item = item.strip()
        if item and item not in items:
            items.append(item)
    return items


def ask_new_source() -> dict:
    """Ask for one source. Every part is needed, so a source can't be left blank."""
    print("\nEnter the source this information came from.")
    title = ask_required("Source title")
    while True:
        url = ask("Web address, starting with http:// or https:// (leave blank to go back): ").strip()
        if not url:
            raise GoBack()
        if re.fullmatch(r"https?://[^\s/]+\.[^\s]+", url):
            break
        print("That doesn't look like a complete web address. Copy it from your browser's address bar, "
              "for example https://www.georgiaencyclopedia.org/articles/...")
    publisher = ask_required("Publisher or website name")
    return {"title": title, "url": url, "publisher": publisher}


def describe_source(source: dict) -> str:
    publisher = f" - {source['publisher']}" if source.get("publisher") else ""
    return f"{source.get('title', '(no title)')}{publisher} ({source.get('url', 'no web address')})"


def same_url(a, b) -> bool:
    return str(a or "").rstrip("/").lower() == str(b or "").rstrip("/").lower()


def add_source_to_figure(figure: dict, source: dict) -> tuple[int, bool]:
    """Add a source to the end of the list. Returns its number and whether it was new.

    Sections and timeline events refer to sources by position, so existing sources are never moved.
    """
    for number, existing in enumerate(figure["sources"], 1):
        if same_url(existing.get("url"), source["url"]):
            return number, False
    figure["sources"].append(source)
    return len(figure["sources"]), True


def ask_figure_sources(figure: dict) -> tuple[list[int], list[str]]:
    """Require at least one source. Returns the source numbers and preview lines for any new source."""
    existing = figure["sources"]
    print(f"\nA source is required. {figure['full_name']}'s current sources:")
    for number, source in enumerate(existing, 1):
        print(f"  {number}. {describe_source(source)}")
    while True:
        answer = ask("Type a source number (or several, like 2,5), or type N to add a new source "
                     "(leave blank to go back): ").strip().lower()
        if not answer:
            raise GoBack()
        if answer == "n":
            source = ask_new_source()
            number, is_new = add_source_to_figure(figure, source)
            if is_new:
                return [number], [f"  New source #{number} added to the end of the list: {describe_source(source)}"]
            print(f"That web address is already source #{number}, so it will be used instead of adding a copy.")
            return [number], []
        parts = [p.strip() for p in answer.split(",") if p.strip()]
        if parts and all(p.isdigit() and 1 <= int(p) <= len(existing) for p in parts):
            return sorted({int(p) for p in parts}), []
        print(f"Please type numbers from 1 to {len(existing)}, or N.")


def ask_web_sources(already: list[dict]) -> list[dict]:
    """Collect sources for a person or FAQ. At least one is required unless some already exist."""
    added = []
    while True:
        if already or added:
            if not ask_yes("Add another source?"):
                return added
        source = ask_new_source()
        if any(same_url(s.get("url"), source["url"]) for s in already + added):
            print("That web address is already listed, so it was not added again.")
        else:
            added.append(source)


# ---------------------------------------------------------------------------
# Finding people
# ---------------------------------------------------------------------------

def pick_record(records: list[dict], kind: str, describe) -> dict:
    """Find a record by part of a name. Nicknames also count, so "Hank" finds Henry Louis Aaron."""
    while True:
        answer = ask_required(f"\nType part of the {kind}'s name")
        terms = simplified(answer).split()
        matches = []
        for record in records:
            names = simplified(" ".join([record.get("full_name", "")] + record.get("also_known_as", [])))
            if all(term in names for term in terms):
                matches.append(record)
        if not matches:
            print(f"No {kind} matches \"{answer}\". Try a shorter part of the name, such as just the last name.")
            continue
        if len(matches) > MAX_MATCHES_SHOWN:
            print(f"{len(matches)} names match. Please type more of the name.")
            continue
        for number, record in enumerate(matches, 1):
            print(f"  {number}. {describe(record)}")
        return matches[ask_choice("Which one?", len(matches)) - 1]


def describe_person(person: dict) -> str:
    details = []
    if person.get("death_year"):
        details.append(f"died {person['death_year']}")
    details.extend(person.get("occupations", [])[:2])
    return person.get("full_name", "(no name)") + (f" ({', '.join(details)})" if details else "")


def describe_figure(figure: dict) -> str:
    return f"{figure.get('full_name', '(no name)')} ({figure.get('lifespan', '')})"


def pick_person(db: dict) -> dict:
    return pick_record(db["people"], "person", describe_person)


def pick_figure(db: dict) -> dict:
    return pick_record(db["prominent_figures"], "prominent figure", describe_figure)


# ---------------------------------------------------------------------------
# Checking the database
# ---------------------------------------------------------------------------

def is_year(value) -> bool:
    return value is None or (isinstance(value, int) and not isinstance(value, bool))


def is_text_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def is_filled_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def source_problems(sources, where: str) -> list[str]:
    if not isinstance(sources, list):
        return [f"{where}: the source list is not in the expected format."]
    problems = []
    for number, source in enumerate(sources, 1):
        if not isinstance(source, dict) or not is_filled_text(source.get("title")):
            problems.append(f"{where}: source #{number} has no title.")
        elif not str(source.get("url") or "").startswith("http"):
            problems.append(f"{where}: source #{number} has no web address starting with http.")
        elif source.get("publisher") is not None and not isinstance(source["publisher"], str):
            problems.append(f"{where}: source #{number} has a publisher that is not text.")
    return problems


def source_number_problems(item: dict, count: int, where: str) -> list[str]:
    numbers = item.get("sources")
    if not isinstance(numbers, list) or not numbers:
        return [f"{where}: it does not list any sources."]
    return [f"{where}: it refers to source number {n!r}, but there are only {count} sources."
            for n in numbers
            if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= count]


def person_problems(person: dict) -> list[str]:
    name = f"{person.get('full_name') or '(no name)'} ({person.get('id') or 'no id'})"
    problems = []
    for field in ("id", "full_name", "biography"):
        if not is_filled_text(person.get(field)):
            problems.append(f"{name}: {field} is missing.")
    if not is_text_list(person.get("occupations")):
        problems.append(f"{name}: occupations is missing or is not a list.")
    for field in ("affiliated_organizations", "also_known_as"):
        if field in person and not is_text_list(person[field]):
            problems.append(f"{name}: {field} is not a list.")
    if person.get("era") not in ALLOWED_ERAS:
        shown = "blank" if person.get("era") is None else f"\"{person['era']}\""
        problems.append(f"{name}: era is {shown}, which is not one of the allowed labels.")
    for field in ("birth_year", "death_year"):
        if not is_year(person.get(field)):
            problems.append(f"{name}: {field} must be a number or empty, but it is {person.get(field)!r}.")
    if "web_sources" in person:
        problems += source_problems(person["web_sources"], name)
    return problems


def figure_problems(figure: dict, person_ids: set) -> list[str]:
    name = f"{figure.get('full_name') or '(no name)'} ({figure.get('id') or 'no id'})"
    problems = []
    for field in ("id", "full_name"):
        if not is_filled_text(figure.get(field)):
            problems.append(f"{name}: {field} is missing.")
    if figure.get("person_id") not in person_ids:
        problems.append(f"{name}: it is linked to {figure.get('person_id')!r}, which is not a person in the database.")
    sources = figure.get("sources", [])
    problems += source_problems(sources, name)
    count = len(sources) if isinstance(sources, list) else 0
    for section in figure.get("sections", []):
        where = f"{name}, section \"{section.get('heading') or '(no heading)'}\""
        if not is_filled_text(section.get("heading")) or not is_filled_text(section.get("text")):
            problems.append(f"{where}: its heading or text is missing.")
        problems += source_number_problems(section, count, where)
    for event in figure.get("timeline", []):
        where = f"{name}, timeline event for {event.get('year') or '(no year)'}"
        if not event.get("year") or not is_filled_text(event.get("event")):
            problems.append(f"{where}: its year or text is missing.")
        problems += source_number_problems(event, count, where)
    return problems


def find_problems(db) -> list[str]:
    """Check the rules for the database. Returns a plain-English list, empty if all is well."""
    if not isinstance(db, dict):
        return ["The database does not have the expected overall structure."]
    problems = []
    for field in ("people", "prominent_figures", "faqs"):
        if not isinstance(db.get(field), list):
            problems.append(f"The {field} list is missing from the database.")
    if problems:
        return problems

    # Every id must be unique across the whole file, whichever part of the file it is in.
    seen = set()
    for key, value in db.items():
        for record in value if isinstance(value, list) else [value]:
            record_id = record.get("id") if isinstance(record, dict) else None
            if record_id in seen:
                problems.append(f"The id {record_id} is used more than once.")
            elif record_id:
                seen.add(record_id)

    people_ok = [p for p in db["people"] if isinstance(p, dict)]
    problems += [f"The people list contains an entry that is not a record."] * (len(db["people"]) - len(people_ok))
    for person in people_ok:
        problems += person_problems(person)
    person_ids = {p.get("id") for p in people_ok}
    for figure in db["prominent_figures"]:
        problems += figure_problems(figure, person_ids)
    for faq in db["faqs"]:
        label = f"FAQ {faq.get('id') or '(no id)'}"
        if not is_filled_text(faq.get("id")) or not is_filled_text(faq.get("q")) or not is_filled_text(faq.get("a")):
            problems.append(f"{label}: its id, question or answer is missing.")
        if "web_sources" in faq:
            problems += source_problems(faq["web_sources"], label)
    return problems


app_modules = None


def load_app_modules() -> dict:
    """Load rag.py, directory.py and featured.py so we can run their real loading code.

    Staff computers may not have the website's add-ons installed, or may be on Python 3.9, which
    can't read the type hints in those files as written. So this reads each file's text and runs it
    with those hints switched off and a stand-in for scikit-learn, which only the chatbot's search
    uses. The loading functions we call are the app's own code, unchanged. Nothing is written to disk.
    """
    global app_modules
    if app_modules is not None:
        return app_modules
    stand_ins = {
        "sklearn": {},
        "sklearn.feature_extraction": {},
        "sklearn.feature_extraction.text": {"ENGLISH_STOP_WORDS": frozenset(), "TfidfVectorizer": None},
        "sklearn.metrics": {},
        "sklearn.metrics.pairwise": {"cosine_similarity": None},
    }
    for name, contents in stand_ins.items():
        module = types.ModuleType(name)
        module.__dict__.update(contents)
        sys.modules[name] = module
    try:
        loaded = {}
        for name in ("rag", "directory", "featured"):
            path = os.path.join(SCRIPT_DIR, f"{name}.py")
            with open(path, encoding="utf-8") as f:
                code = compile(f.read(), path, "exec", flags=future_flags.annotations.compiler_flag, dont_inherit=True)
            module = types.ModuleType(name)
            module.__file__ = path
            sys.modules[name] = module
            exec(code, module.__dict__)
            loaded[name] = module
    finally:
        for name in stand_ins:
            sys.modules.pop(name, None)
    app_modules = loaded
    return loaded


def run_all_checks(path: str) -> tuple[list[str], list[str]]:
    """Check the file on disk. Returns (problems, informational lines)."""
    try:
        with open(path, "rb") as f:
            db = json.loads(f.read().decode("utf-8"))
    except (OSError, ValueError):
        log_error()
        return ["The database file can't be opened or is not valid JSON, so nothing else could be checked."], []

    problems = find_problems(db)
    info = ["The file is valid JSON."]
    try:
        modules = load_app_modules()
    except Exception:
        log_error()
        # This says something about the app's files, not about the data, so it isn't a data problem.
        info.append("Could not load the app's code for its own test, so that test was skipped. "
                    "Please tell the maintainer.")
        return problems, info

    tests = [
        ("rag.py", "chatbot text chunks", lambda: modules["rag"].load_json_chunks(path)),
        ("directory.py", "people in the directory", lambda: modules["directory"].load_people(path)),
        ("directory.py", "prominent figure profiles", lambda: modules["directory"].load_prominent(path)),
        ("featured.py", "people eligible for the monthly feature", lambda: modules["featured"]._eligible_people(path)),
    ]
    for filename, what, load in tests:
        try:
            info.append(f"{filename} loaded {len(load())} {what}.")
        except Exception:
            log_error()
            problems.append(f"The website's {filename} could not read the database while loading {what}.")
    return problems, info


# ---------------------------------------------------------------------------
# Reading and saving safely
# ---------------------------------------------------------------------------

def load_database(path: str) -> tuple[bytes, dict]:
    """Read the database. Returns its exact bytes as well, for checking and backups."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
        db = json.loads(raw.decode("utf-8"))
    except OSError:
        log_error()
        raise FriendlyError(f"The database file could not be opened: {path}\n"
                            "Check that you are in the project folder and that the file exists, then try again.")
    except ValueError:
        log_error()
        raise FriendlyError("The database file is damaged, so nothing can be added right now.\n"
                            "Ask the maintainer to restore the newest copy from the backups folder.")
    if not isinstance(db, dict) or not all(isinstance(db.get(k), list) for k in ("people", "prominent_figures", "faqs")):
        raise FriendlyError("The database file does not have the expected structure, so nothing can be added.\n"
                            "Ask the maintainer to restore the newest copy from the backups folder.")
    return raw, db


def to_file_bytes(db: dict) -> bytes:
    """The same formatting the file already has: indent=2, real accented letters, no newline at the end."""
    return json.dumps(db, indent=2, ensure_ascii=False).encode("utf-8")


def write_safely(path: str, data: bytes) -> None:
    """Write a temporary file and then swap it into place, so a crash can't leave a half-written file."""
    handle, temp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), prefix=".add_content_", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as f:  # binary, so Windows doesn't change the line endings
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(path):
            shutil.copymode(path, temp_path)
        os.replace(temp_path, path)
    except BaseException:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def make_backup(path: str, raw: bytes) -> str:
    """Save a timestamped copy. Never overwrites an older backup from the same minute."""
    folder = os.path.join(os.path.dirname(os.path.abspath(path)), "backups")
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    stamp = f"{stem}_{datetime.datetime.now():%Y-%m-%d_%H%M}"
    backup_path = os.path.join(folder, f"{stamp}.json")
    attempt = 1
    while True:
        try:
            with open(backup_path, "xb") as f:
                f.write(raw)
            break
        except FileExistsError:
            attempt += 1
            backup_path = os.path.join(folder, f"{stamp}_{attempt}.json")
    with open(backup_path, "rb") as f:
        if f.read() != raw:
            raise OSError("the backup does not match the original")
    return backup_path


def restore_backup(path: str, backup_path: str, raw: bytes) -> None:
    """Put the backup back and tell the person what happened, including if that also fails."""
    try:
        write_safely(path, raw)
        with open(path, "rb") as f:
            if f.read() != raw:
                raise OSError("the restored file does not match the backup")
        print("The database was automatically restored from the backup, so it is back to how it was. "
              "Your change was NOT saved.")
    except Exception:
        log_error()
        print("IMPORTANT: The automatic restore did not work, and the database may be damaged.\n"
              f"Do not make more changes. Give the maintainer this backup file: {backup_path}")


def save_change(path: str, raw: bytes, db: dict, preview: list[str]) -> bool:
    """Preview, confirm, back up, write, re-check, and restore if the check finds anything new."""
    print("\n" + "=" * 70 + "\nPlease review. This is exactly what will be saved:\n")
    print("\n".join(preview))
    print("\n" + "=" * 70)
    if ask("Save this change? (yes/no): ").strip().lower() != "yes":
        print("Cancelled. Nothing was changed.")
        return False

    new_bytes = to_file_bytes(db)
    with open(path, "rb") as f:
        if f.read() != raw:
            raise FriendlyError("Nothing was saved, because someone or something else changed the database "
                                "while you were working.\nPlease choose the option again to redo your change.")

    # Older problems shouldn't undo this person's work. Only problems this change caused trigger a restore.
    problems_before, _ = run_all_checks(path)

    try:
        backup_path = make_backup(path, raw)
    except OSError:
        log_error()
        raise FriendlyError("Nothing was saved, because a backup could not be made.\n"
                            "Check that the computer has free disk space and that you can save in this folder, "
                            "then try again.")

    try:
        write_safely(path, new_bytes)
        problems_after, info = run_all_checks(path)
    except (Exception, KeyboardInterrupt):
        log_error()
        print("\nSomething went wrong while saving.")
        restore_backup(path, backup_path, raw)
        print("Please try again, or give the maintainer the file backups/last_error.txt.")
        return False

    new_problems = [p for p in problems_after if p not in problems_before]
    if new_problems:
        print("\nThe check after saving found a problem with this change:")
        for problem in new_problems:
            print(f"  - {problem}")
        restore_backup(path, backup_path, raw)
        print("Please give the maintainer this message before trying again.")
        return False

    print(f"\nSaved and checked. Backup made: {backup_path}")
    for line in info:
        print(f"  {line}")
    if problems_after:
        print(f"  Note: {len(problems_after)} older problem(s) are still in the database. "
              "Your change did not cause them. Choose option 7 to see them.")
    print(NEXT_STEPS)
    return True


# ---------------------------------------------------------------------------
# The menu options
# ---------------------------------------------------------------------------

def figure_with_sources(db: dict) -> dict:
    figure = pick_figure(db)
    figure.setdefault("sources", [])
    return figure


def add_section(path: str) -> None:
    raw, db = load_database(path)
    figure = figure_with_sources(db)
    heading = ask_own_words("Section heading")
    text = ask_own_words("Section text", long_text=True)
    numbers, source_lines = ask_figure_sources(figure)
    figure.setdefault("sections", []).append({"heading": heading, "text": text, "sources": numbers})
    preview = [f"Add a new section to the end of {figure['full_name']}'s profile:",
               f"  Heading: {heading}"]
    preview += wrapped("Text", text)
    preview += [f"  Cited sources: {', '.join(map(str, numbers))}"] + source_lines
    save_change(path, raw, db, preview)


def year_for_sorting(year):
    match = re.search(r"\d{4}", str(year))
    return int(match.group()) if match else None


def add_timeline_event(path: str) -> None:
    raw, db = load_database(path)
    figure = figure_with_sources(db)
    while True:
        # Years are stored as text in this file, and some are not exact, like "1960s".
        year = ask_required("\nYear of the event, such as 1968 or 1960s")
        if re.fullmatch(r"\d{4}s?", year):
            break
        print("Please type a four-digit year, such as 1968, or a decade, such as 1960s.")
    event_text = ask_own_words("What happened (one or two sentences)")
    numbers, source_lines = ask_figure_sources(figure)

    # Insert after the last event at or before this year. Existing events keep their order.
    timeline = figure.setdefault("timeline", [])
    position = 0
    for index, event in enumerate(timeline):
        event_year = year_for_sorting(event.get("year"))
        if event_year is not None and event_year <= year_for_sorting(year):
            position = index + 1
    timeline.insert(position, {"year": year, "event": event_text, "sources": numbers})

    preview = [f"Add a timeline event for {figure['full_name']}:", f"  Year: {year}"]
    preview += wrapped("Event", event_text)
    preview += [f"  Cited sources: {', '.join(map(str, numbers))}"] + source_lines
    if position > 0:
        preview.append(f"  It will go right after: {timeline[position - 1]['year']}")
    else:
        preview.append("  It will go first in the timeline.")
    save_change(path, raw, db, preview)


def add_source_link(path: str) -> None:
    raw, db = load_database(path)
    figure = figure_with_sources(db)
    source = ask_new_source()
    number, is_new = add_source_to_figure(figure, source)
    if not is_new:
        print(f"That web address is already source #{number} for {figure['full_name']}, so nothing needs adding.")
        return
    save_change(path, raw, db, [f"Add source #{number} to the end of {figure['full_name']}'s source list:",
                                f"  {describe_source(source)}"])


def next_id(records: list[dict], prefix: str, digits: int) -> str:
    """One more than the highest number in use, so an id that was ever used is never reused."""
    numbers = [int(m.group(1)) for r in records for m in [re.fullmatch(rf"{prefix}_(\d+)", str(r.get("id")))] if m]
    return f"{prefix}_{max(numbers, default=-1) + 1:0{digits}d}"


def update_count(db: dict, field: str, new_count: int) -> list[str]:
    """Keep the totals at the top of the file correct, and mention it in the preview."""
    meta = db.get("database_meta")
    if not isinstance(meta, dict) or field not in meta:
        return []
    old_count, meta[field] = meta[field], new_count
    return [f"  Also updates the database's total ({field.replace('_', ' ')}) from {old_count} to {new_count}."]


def similar_questions(question: str, faqs: list[dict]) -> list[str]:
    words = lambda text: set(re.findall(r"[a-z0-9'-]+", simplified(text)))
    found = []
    for faq in faqs:
        existing = faq.get("q", "")
        a, b = words(question), words(existing)
        overlap = len(a & b) / max(len(a | b), 1)
        if overlap >= 0.6 or difflib.SequenceMatcher(None, simplified(question), simplified(existing)).ratio() >= 0.75:
            found.append(existing)
    return found


def add_faq(path: str) -> None:
    raw, db = load_database(path)
    question = ask_own_words("Question")
    similar = similar_questions(question, db["faqs"])
    if similar:
        print("\nA very similar question already exists:")
        for existing in similar[:5]:
            print(f"  - {existing}")
        if not ask_yes("Add your question anyway?"):
            raise GoBack()
    answer = ask_own_words("Answer", long_text=True)
    sources = ask_web_sources([])
    faq = {"id": next_id(db["faqs"], "faq", 3), "type": "faq", "q": question, "a": answer,
           "web_sources": sources, "added_by": STAFF_TAG}
    db["faqs"].append(faq)
    preview = ["Add a new frequently asked question:", f"  Question: {question}"]
    preview += wrapped("Answer", answer)
    preview += [f"  Source: {describe_source(s)}" for s in sources]
    preview += update_count(db, "faq_pairs", len(db["faqs"]))
    save_change(path, raw, db, preview)


def usual_era(people: list[dict], death_year) -> str | None:
    """The era existing records use for this death year, if they show a clear pattern."""
    if death_year is None:
        return None
    for era in ALLOWED_ERAS:
        years = [p["death_year"] for p in people if p.get("era") == era and p.get("death_year")]
        if years and min(years) <= death_year <= max(years):
            return era
    return None


def add_person(path: str) -> None:
    raw, db = load_database(path)
    full_name = ask_required("\nFull name")
    close = [p for p in db["people"]
             if difflib.SequenceMatcher(None, simplified(full_name), simplified(p.get("full_name", ""))).ratio() >= 0.9]
    if close:
        print("\nThis person may already be in the database:")
        for person in close:
            print(f"  - {describe_person(person)}")
        print("If so, choose option 6 instead, to update their biography.")
        if not ask_yes("Add a new person anyway?"):
            raise GoBack()

    words = [w for w in full_name.split() if w.rstrip(".,").lower() not in ("jr", "sr", "ii", "iii", "iv")]
    guess = words[-1] if words else full_name
    last_name = clean_text(ask(f"Last name (press Enter to use \"{guess}\"): ")) or guess

    birth_year = ask_year("Birth year")
    while True:
        death_year = ask_year("Death year")
        if birth_year is None or death_year is None or death_year >= birth_year:
            break
        print(f"The death year can't be before the birth year ({birth_year}). Please check it.")

    print("\nEra:")
    for number, era in enumerate(ALLOWED_ERAS, 1):
        print(f"  {number}. {era}")
    hint = usual_era(db["people"], death_year)
    if hint:
        print(f"Existing records with the death year {death_year} are labelled: {hint}")
    era = ALLOWED_ERAS[ask_choice("Which era?", len(ALLOWED_ERAS)) - 1]

    occupations = ask_list("Occupations")
    organizations = ask_list("Organizations")
    biography = ask_own_words("Biography", long_text=True)
    sources = ask_web_sources([])

    person = {"id": next_id(db["people"], "person", 4), "type": "buried_person",
              "full_name": full_name, "last_name": last_name}
    if birth_year is not None:
        person["birth_year"] = birth_year
    person.update({"death_year": death_year, "era": era, "occupations": occupations,
                   "affiliated_organizations": organizations, "biography": biography,
                   "web_sources": sources, "added_by": STAFF_TAG})
    db["people"].append(person)

    preview = ["Add a new person to the directory:",
               f"  Full name: {full_name}",
               f"  Last name: {last_name}",
               f"  Birth year: {birth_year if birth_year is not None else '(blank)'}",
               f"  Death year: {death_year if death_year is not None else '(blank)'}",
               f"  Era: {era}",
               f"  Occupations: {', '.join(occupations) or '(none)'}",
               f"  Organizations: {', '.join(organizations) or '(none)'}"]
    preview += wrapped("Biography", biography)
    preview += [f"  Source: {describe_source(s)}" for s in sources]
    preview += update_count(db, "total_person_records", len(db["people"]))
    if not occupations or len(biography) < FEATURED_MIN_BIO:
        preview.append(f"  Note: they will be in the directory, but can't appear as a monthly featured person "
                       f"without an occupation and a biography of {FEATURED_MIN_BIO}+ characters.")
    save_change(path, raw, db, preview)


def update_biography(path: str) -> None:
    raw, db = load_database(path)
    person = pick_person(db)
    print("\nCurrent biography:")
    print("\n".join(wrapped(person["full_name"], person.get("biography", ""))))
    is_prominent = any(f.get("person_id") == person["id"] for f in db["prominent_figures"])
    if is_prominent:
        print("\nNote: this person also has a full profile page. This changes only their short biography, "
              "not the profile page. Use options 1-3 for the profile.")

    new_bio = ask_own_words("New biography", long_text=True)
    if new_bio == person.get("biography"):
        print("That is the same as the current biography, so nothing needs changing.")
        return

    existing = person.get("web_sources", [])
    if existing:
        print("\nThis person's current sources will be kept:")
        for source in existing:
            print(f"  - {describe_source(source)}")
        added = ask_web_sources(existing)
    else:
        print("\nA source for the new biography is required.")
        added = ask_web_sources([])

    old_bio = person.get("biography", "")
    person["biography"] = new_bio  # the "source" field is left exactly as it was
    if added:
        person["web_sources"] = existing + added

    preview = [f"Change the biography of {person['full_name']}.", "", "BEFORE:"]
    preview += wrapped("Biography", old_bio) + ["", "AFTER:"] + wrapped("Biography", new_bio) + [""]
    preview += [f"  New source: {describe_source(s)}" for s in added]
    if added and not existing:
        preview.append("  Note: the live site will now credit this source for this person instead of "
                       "the Henderson book.")
    save_change(path, raw, db, preview)


def check_database(path: str) -> None:
    """Option 7. Only reads the file."""
    print("\nChecking the database. This does not change anything.\n")
    problems, info = run_all_checks(path)
    for line in info:
        print(f"  {line}")
    if not problems:
        print("\nNo problems found.")
        return
    print(f"\nFound {len(problems)} problem(s):")
    for problem in problems:
        print(f"  - {problem}")
    print("\nNothing was changed. Please give this list to the maintainer.")


ACTIONS = {"1": add_section, "2": add_timeline_event, "3": add_source_link, "4": add_faq,
           "5": add_person, "6": update_biography, "7": check_database}


def run_menu(path: str) -> None:
    print("\n" + textwrap.fill(WELCOME, width=88))
    while True:
        print(MENU)
        choice = ask("Type a number, or q to quit: ").strip().lower()
        if choice not in ACTIONS:
            print("Please type a number from 1 to 7, or q to quit.")
            continue
        try:
            ACTIONS[choice](path)
        except GoBack:
            print("Going back to the menu. Nothing was changed.")
        except FriendlyError as problem:
            print(f"\n{problem}")
        except QuitProgram:
            raise
        except Exception:
            log_error()
            print("\nSomething unexpected went wrong, and nothing was saved.\n"
                  "Please try again. If it happens again, give the maintainer the file backups/last_error.txt.")
        ask("\nPress Enter to return to the menu. ")


def main() -> int:
    global error_log_path
    if sys.version_info < (3, 9):
        print("This tool needs Python 3.9 or newer. Please ask the maintainer to update Python on this computer.")
        return 1
    try:
        sys.stdout.reconfigure(errors="replace")  # a name with an unusual letter must not stop the tool
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="Add content to the South-View database through a text menu.")
    parser.add_argument("--file", default=DEFAULT_DB, help="use a copy of the database instead (for testing)")
    path = os.path.abspath(parser.parse_args().file)
    error_log_path = os.path.join(os.path.dirname(path), "backups", "last_error.txt")

    try:
        if not os.path.isfile(path):
            print(f"The database file could not be found: {path}\n"
                  "Check that add_content.py is still in the project folder next to it, then try again.")
            return 1
        run_menu(path)
    except (QuitProgram, KeyboardInterrupt):
        print("\nGoodbye. Nothing else was changed.")
    except Exception:
        log_error()
        print("\nSomething unexpected went wrong, so the tool stopped. Nothing else was changed.\n"
              "Please give the maintainer the file backups/last_error.txt.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

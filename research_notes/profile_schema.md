# Prominent figure profile format

Write a JSON array (UTF-8, valid JSON, no comments) with one object per person:

{
  "id": "pf_<lowercase_surname_or_short_name>",          e.g. "pf_herndon", "pf_king_sr", "pf_alberta_king"
  "person_id": "<existing id or null>",                   given to you below; null only for people not in the book
  "full_name": "<exact name given below>",
  "also_known_as": ["..."],                                nicknames/short names, may be []
  "birth_year": 1858,                                      integer, best-supported value
  "death_year": 1927,                                      integer
  "lifespan": "June 26, 1858 – July 21, 1927",             human-readable; use only the year where the day is unknown
  "tagline": "One line, max 110 characters, what they are remembered for",
  "occupations": ["Entrepreneur", "Philanthropist"],
  "burial": "1-2 sentences on their burial or memorial at South-View, with the evidence level stated plainly (e.g. 'Reported by ...').",
  "sections": [
    {"heading": "Early life and family", "text": "...", "sources": [1, 3]},
    {"heading": "Education", ...},
    {"heading": "Career and achievements", ...},
    {"heading": "Civil rights and civic life", ...},        omit a section if there is nothing sourced for it
    {"heading": "Legacy and honors", ...},
    {"heading": "Did you know?", ...},                       3-5 short facts in one paragraph
    {"heading": "Where sources disagree", ...}               only if the notes flag conflicts; name which source says what
  ],
  "timeline": [{"year": "1905", "event": "Founded the Atlanta Mutual Insurance Association.", "sources": [2]}],
  "sources": [{"title": "Alonzo Herndon", "url": "https://...", "publisher": "New Georgia Encyclopedia"}]
}

Rules:
- Use ONLY facts in the research notes, each backed by a URL in the notes. Do not add facts from memory.
- "sources" numbers are 1-based indexes into that person's own "sources" array. Every section and timeline item needs at least one.
- Section text: plain prose, no markdown, 60-220 words each. Write so each section makes sense on its own (repeat the person's name rather than "he"/"she" at the start), because sections are retrieved individually by a search engine.
- Where sources conflict, use the best-supported value in the main text and explain the conflict in "Where sources disagree".
- Facts the notes mark as coming only from a search snippet or unverified may be included only if worded with that caveat ("reportedly", "according to ..."), or left out.
- Prefer authoritative URLs (encyclopedias, archives, major newspapers) in the sources list; include Find a Grave only for burial evidence.
- Timeline: 6-15 entries, chronological, "year" as a string.

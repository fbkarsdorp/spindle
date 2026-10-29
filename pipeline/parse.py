"""Parse the ruthenia.ru HTML edition of Thompson's Motif-Index into clean JSON.

The ruthenia pages are the most complete digital transcription of the revised
edition (1955-58) we know of: they preserve the italicised motif headline, the
explanatory note and the full bibliographical apparatus. Their only systematic
defect is that the original Latin-1 text was once decoded as Windows-1251, so
that e.g. 'Métraux' reads 'Mйtraux'. That mapping is a bijection and is undone
here character by character.

Output: data/build/motifs.json and data/build/sections.json
"""

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "ruthenia"
OUT = ROOT / "data" / "build"

LETTERS = "ABCDEFGHJKLMNPQRSTUVWXZ"

CATEGORY_NAMES = {
    "A": "Mythological Motifs",
    "B": "Animals",
    "C": "Tabu",
    "D": "Magic",
    "E": "The Dead",
    "F": "Marvels",
    "G": "Ogres",
    "H": "Tests",
    "J": "The Wise and the Foolish",
    "K": "Deceptions",
    "L": "Reversal of Fortune",
    "M": "Ordaining the Future",
    "N": "Chance and Fate",
    "P": "Society",
    "Q": "Rewards and Punishments",
    "R": "Captives and Fugitives",
    "S": "Unnatural Cruelty",
    "T": "Sex",
    "U": "The Nature of Life",
    "V": "Religion",
    "W": "Traits of Character",
    "X": "Humor",
    "Z": "Miscellaneous Groups of Motifs",
}

ID = r"[A-Z]\d+(?:\.\d+)*"
MOTIF_RE = re.compile(rf"^({ID})\.?\s+({ID})\.?\s*(.*)$", re.S)
SECTION_RE = re.compile(rf"^({ID})\.?\s*(?:-+|–|—)\s*({ID})\.?\s+(.+)$", re.S)
HEADING_RE = re.compile(rf"^({ID})\.\s+(\D.*)$", re.S)


def fix_mojibake(text: str) -> str:
    out = []
    for ch in text:
        if "Ѐ" <= ch <= "ӿ":
            try:
                ch = ch.encode("cp1251").decode("cp1252")
            except UnicodeError:
                pass
        out.append(ch)
    return "".join(out)


def tidy(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def segments(p: Tag):
    """Flatten a paragraph into (text, italic) runs, merging neighbours."""
    runs = []

    def walk(node, italic):
        for child in node.children:
            if isinstance(child, NavigableString):
                runs.append([str(child), italic])
            elif isinstance(child, Tag):
                walk(child, italic or child.name in ("i", "em"))

    walk(p, False)
    merged = []
    for text, italic in runs:
        text = fix_mojibake(text)
        if merged and (merged[-1][1] == italic or not text.strip()):
            merged[-1][0] += text
        else:
            merged.append([text, italic])
    return [(t, i) for t, i in merged]


def plain(p: Tag) -> str:
    return tidy("".join(t for t, _ in segments(p)))


CF_RE = re.compile(r"\(\s*[Cc]f\.?\s*([^)]*)\)")
REF_ID_RE = re.compile(rf"(?<![A-Za-z]){ID}(?:\s*[-–]+\s*{ID})?")
TYPE_RE = re.compile(r"\bTypes?\s+((?:\d+[A-Z*]*(?:\s*[,–\-]\s*|\s+and\s+|\s+|\b))+)")


def is_prose(sentence: str) -> bool:
    s = CF_RE.sub("", sentence).strip()
    if not s or re.search(r"[:*]|\d|\bTypes?\b|\bFb\b|\bBP\b|\bDh\b|\bibid\b|\bsee\b", s):
        return False
    words = s.split()
    if len(words) < 3 or not any(len(w) >= 4 and w.isalpha() and w.islower() for w in words):
        return False
    lower = sum(1 for w in words[1:] if w[:1].islower() or not w[:1].isalpha())
    return lower >= 0.6 * (len(words) - 1)


def split_note(text: str):
    """Split leading prose (an explanatory note) from bibliography."""
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z*(“\"])", text)
    taken = []
    for s in sentences:
        if not is_prose(s):
            break
        taken.append(s)
    note = " ".join(taken)
    return note, text[len(note):].strip()


def split_tail(after: str):
    """Return (note, references) for the text that follows the headline."""
    if after.startswith("--"):
        return "", after[2:].strip()
    pre, sep, post = after.partition("--")
    note, rest = split_note(pre.strip())
    if not note:
        return "", after
    refs = rest
    if post.strip():
        refs = (rest + "--" if rest else "") + post.strip()
    return note, refs


def extract_cf(text: str):
    ids = []
    for m in CF_RE.finditer(text):
        for r in REF_ID_RE.findall(m.group(1)):
            r = re.sub(r"\s+", "", r).rstrip(".")
            ids.append(r)
    return ids


def extract_types(text: str):
    out = []
    for m in re.finditer(r"\*?Types?\s+([\d][\dA-Z*,\s\-–]*)", text):
        for t in re.findall(r"\d+[A-Z]?\*?", m.group(1)):
            out.append(t)
    seen, uniq = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


ABBREV = re.compile(r"(?:\b(?:a|p|m|i\.e|e\.g|cf|Cf|St|Mr|Mrs|Dr|No|vs|viz|ca|lit|Fr|Ger|Ir|Sp|ff)|\b[A-Z])\.$")

REF_START = re.compile(r"\*?[A-Z][\w.]*(?:\s[\w.()]+){0,3}:\s")


def complete_title(title: str, after: str):
    """The italics of the headline sometimes end before the headline does
    ('Fairy wins kiss in game;' + roman 'embraces woman and flies off...').
    Extend the headline to the end of its sentence."""
    # punctuation that leaked out of the italics
    if after and after[0] in ".?!" and not title.endswith((".", "?", "!")):
        title += after[0]
        after = after[1:].strip()
    # a cross-reference that slipped into the italics: 'Ghost of fox (Cf.'
    m = re.search(r"\s*\((?:[Cc]f)\.?$", title)
    if m:
        return title[: m.start()].rstrip(), title[m.start():].strip() + " " + after
    finished = re.search(r"[.?!][\"”“’)]*$", title) and not ABBREV.search(title)
    if after[:1].islower():
        finished = False
    if finished or not after:
        return title, after
    if after.startswith("--") or re.match(r"^\(?[Cc]f\.", after):
        return title, after
    # consume the tail up to the end of the sentence (or a '--' separator)
    i = 0
    while i < len(after):
        if after.startswith("--", i) or (after[i - 1:i] == " " and REF_START.match(after, i)):
            return tidy(title + " " + after[:i]), after[i:].strip()
        ch = after[i]
        if ch in ".?!":
            j = i + 1
            while j < len(after) and after[j] in "\"”“’)":
                j += 1
            head = after[:j]
            if (j == len(after) or after[j] == " ") and not ABBREV.search(title + " " + head):
                return tidy(title + " " + head), after[j:].strip()
        i += 1
    return title, after


def smart_quotes(text: str) -> str:
    """Normalise the erratic curly quotes of the transcription."""
    text = re.sub(r"(?<=\w)[‘’'](?=\w)", "’", text)
    text = re.sub(r"(?<=s)[‘’'](?=\s|[,.;:)]|$)", "’", text)
    out = []
    for i, ch in enumerate(text):
        if ch in "“”\"":
            prev = text[i - 1] if i else " "
            ch = "“" if prev in " ([—-:;" or i == 0 else "”"
        elif ch in "‘'" or (ch == "’" and not (i and text[i - 1].isalnum() and i + 1 < len(text) and text[i + 1].isalnum())):
            prev = text[i - 1] if i else " "
            if not (i and text[i - 1].isalnum()):
                ch = "‘" if prev in " ([—-:;“" or i == 0 else "’"
            else:
                ch = "’"
        out.append(ch)
    return "".join(out)


def parse_letter(letter: str):
    html = (RAW / f"{letter.lower()}.htm").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    motifs, sections, headings = [], [], []
    for p in soup.find_all("p"):
        text = plain(p)
        if not text or not text[0] == letter:
            continue
        m = MOTIF_RE.match(text)
        if m and m.group(1).rstrip(".") == m.group(2).rstrip("."):
            mid = m.group(1).rstrip(".")
            segs = segments(p)
            # drop the doubled identifier from the run list
            # locate first italic run that carries words
            title, after = None, None
            consumed = ""
            for idx, (t, it) in enumerate(segs):
                if it and re.search(r"[A-Za-z]", t):
                    title = tidy(t)
                    after = "".join(x for x, _ in segs[idx + 1:])
                    break
                consumed += t
            if title is None:
                # headline set in bold or roman: take the first sentence
                rest = m.group(3)
                mm = re.match(r"(.+?[.?!])(?:\s|--|$)(.*)$", rest, re.S)
                if mm:
                    title, after = mm.group(1), mm.group(2)
                else:
                    title, after = rest, ""
            title = tidy(title)
            after = tidy(after or "")
            title, after = complete_title(title, after)
            note, refs = split_tail(after)
            motifs.append(
                {
                    "id": mid,
                    "title": smart_quotes(title.replace("--", "—")),
                    "note": smart_quotes(note.replace("--", "—")),
                    "refs": smart_quotes(refs.replace("--", "—")),
                    "cf": extract_cf(note + " " + refs),
                    "types": extract_types(refs + " " + note),
                }
            )
            continue
        s = SECTION_RE.match(text)
        if s:
            lo, hi = s.group(1), s.group(2)
            if lo[0] == hi[0] == letter:
                sections.append({"lo": lo, "hi": hi, "title": tidy(s.group(3)).rstrip(".")})
            continue
        h = HEADING_RE.match(text)
        if h and len(text) < 160:
            headings.append({"id": h.group(1), "title": tidy(h.group(2)).rstrip(".")})
    return motifs, sections, headings


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_motifs, all_sections, all_headings = [], [], []
    for letter in LETTERS:
        m, s, h = parse_letter(letter)
        print(f"{letter}: {len(m):5d} motifs {len(s):4d} sections {len(h):4d} headings", file=sys.stderr)
        all_motifs += m
        all_sections += s
        all_headings += h
    # de-duplicate (a handful of motifs are printed twice)
    seen, uniq = {}, []
    for m in all_motifs:
        if m["id"] in seen:
            prev = seen[m["id"]]
            if len(m["refs"]) + len(m["note"]) > len(prev["refs"]) + len(prev["note"]) and m["title"] == prev["title"]:
                prev.update(m)
            elif m["title"] != prev["title"]:
                prev.setdefault("alt_titles", []).append(m["title"])
            continue
        seen[m["id"]] = m
        uniq.append(m)
    secs = {(s["lo"], s["hi"]): s for s in all_sections}
    heads = {}
    for h in all_headings:
        heads.setdefault(h["id"], h)
    json.dump(uniq, open(OUT / "motifs.raw.json", "w"), ensure_ascii=False, indent=0)
    json.dump({"sections": list(secs.values()), "headings": list(heads.values()), "categories": CATEGORY_NAMES},
              open(OUT / "sections.json", "w"), ensure_ascii=False, indent=1)
    print(f"total {len(uniq)} motifs, {len(secs)} sections, {len(heads)} headings", file=sys.stderr)


if __name__ == "__main__":
    main()

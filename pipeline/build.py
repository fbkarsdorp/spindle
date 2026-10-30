"""Assemble the parsed motifs into a tree and enrich them.

Adds to every motif: its parent and ancestors (sections and group motifs), the
cultures/traditions named in its references (normalised and grouped into
regions), tale types, validated cross-references, and the text that will be
embedded.

Input:  data/build/motifs.raw.json, data/build/sections.json, data/raw/tmi-index.txt
Output: data/build/tmi.json
"""

import json
import re
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "data" / "build"

# A few headlines that the transcription garbles beyond what the parser can mend.
PATCHES = {
    "B490": {"title": "Other helpful animals."},
    "X700": {"title": "Humor concerning sex."},
    "B739": {"title": "Fanciful color, smell, etc. of animals—miscellaneous.", "refs": ""},
    "D1171.7": {"title": "Magic vase.", "refs": "*Chauvin V 259 No. 154; India: Thompson-Balys; Chinese: Werner 348."},
    "J182.1": {"title": "“Forty-nine gates of wisdom” open to Moses (and Solomon).", "refs": "Jewish: *Neuman."},
    "J1191.1.1": {"title": "“The sea is on fire” not more absurd than the decision about the colt.", "refs": "India: *Thompson-Balys."},
    "J2033": {"title": "Three girls distressed by seemingly impossible task of going and returning together—one in half month, other in fifteen days, other in seven plus eight days.", "refs": "Chinese: Graham."},
    "Z39.9": {"title": "Series of things acquired by mouse.", "note": "“You cannot have this but you may have that instead,” etc. Clod—fish—cakes—kid—goat—drum—girl. Girl kills mouse accidentally.", "refs": "India: Thompson-Balys."},
}


def num(mid: str) -> int:
    return int(re.match(r"[A-Z](\d+)", mid).group(1))


def letter(mid: str) -> str:
    return mid[0]


def titlecase(s: str) -> str:
    small = {"and", "or", "of", "the", "in", "to", "a", "an", "for", "by", "with", "on", "from"}
    if s.isupper():
        words = s.lower().split()
        return " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(words))
    return s


def tidy_heading(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip().rstrip(".").strip()
    s = s.replace("--", "—").replace(" - ", "—")
    return titlecase(s)


# ---------------------------------------------------------------------------
# Cultures
# ---------------------------------------------------------------------------

REGIONS = [
    ("Celtic", r"irish|ireland|welsh|wales|scot|breton|celtic|manx|cornish|gaelic|highland"),
    ("Northern Europe", r"icel|norse|danish|denmark|norw|swed|faroe|finn|lapp|esth|eston|livon|lithuan|lett|latvia|scandinav|eddic|saga"),
    ("Western Europe", r"english|england|german(?! new guinea)|swiss|switz|austria|tirol|tyrol|flemish|dutch|holland|belg|(?<!missouri )french(?! canad)|france|gascon|lorraine|italian|italy|sicil|tuscan|spanish|spain|catalan|portug|basque|romance|exempl|mediaeval|medieval|european|europe|fabliau|prussian|germanic|frisian|walloon|novella"),
    ("Eastern Europe", r"russia|slav|czech|bohem|polish|poland|serb|croat|bulgar|ruman|romania|hungar|magyar|cherem|mordvin|votyak|wotjak|ukrain|slovak|slovene|wend|ossete|circassia|georgian(?! negro)|caucas|gypsy|yugoslav|albania|greek modern"),
    ("Mediterranean & Near East", r"greek|roman|etrusc|western asia|latin|jewish|hebrew|talmud|rabbin|arab|persia|babylon|assyr|egypt|turk|armenia|syria|sumer|hittite|semitic|islam|moham|koran|bible|biblical|palestin|iran|kurd|berber|moroc|algeri|tunis|cypr|byzant"),
    ("South Asia", r"india(?!n)|east indian|hindu|buddh|ceylon|sinhal|bengal|panjab|punjab|tamil|kashmir|santal|deccan|tibet|nepal|jataka|panchatantra|sanskrit|\bpali\b|\bgond|bihar|\bassam|oraon|\bmunda\b|\bkota\b|\btoda\b"),
    ("East Asia", r"chin(?!cha|ook)|japan|korea|ainu|indo-chin|annam|burm|siam|thai|cambod|viet|laos|mongol(?!ian\b)|manchu|formosa|taiwan"),
    ("Siberia & Central Asia", r"siberia|buriat|koryak|yakut|chukch|yukag|tatar|kalm|kirg|kazak|altai|samoyed|ostyak|vogul|gilyak|tungus|mongolian|turkest|ural"),
    ("Arctic", r"eskimo|greenland|aleut|inuit"),
    ("Oceania", r"hawai|tahiti|tonga|maori|new zealand|marques|tuamotu|samoa|polynes|melanes|micrones|new hebrid|new guinea|papua|(?<!western )mono\b|\balu\b|buin|fiji|indones|philipp|filipin|tinguian|borneo|sumatra|java|\bbali\b|celebes|malay|austral|easter is|cook is|marshall|(?<!north )(?<!south )carolin|gilbert|new britain|new ireland|solomon|oceani|banks is|torres|admiralty|trobriand|chatham|mangaia|rarotonga|niue|caroline|gilbert|truk|guam|madagascar|malagasy|lepers is|\bnias\b|dyak|batak|mentawei|andaman|nicobar|\bkei\b"),
    ("Africa", r"africa|ekoi|fang|zulu|hottentot|bushman|benga|ila\b|ibo|kaffir|zanzibar|hausa|yoruba|congo|gold coast|vai\b|liberia|cape verde|basuto|angola|cameroon|fjort|duala|mpongwe|swahili|luba|thonga|togo|wute|wachaga|bulu|bushongo|ganda|ba ronga|kordofan|loango|bankon|upoto|wakweli|nigeria|sudan|ethiop|abyssin|somali|kenya|uganda|ashanti|dahomey|\bewe\b|kikuyu|masai|nyanja|herero|lamba|\bbena\b|\btanga\b|sotho|xhosa|bantu|nandi|\bkamba\b|ronga|nuer|dinka|shilluk|chaga|baganda|\bbasa\b|gbaya|kpelle"),
    # Latin America first: its "south american indian" must win over North America's "american indian"
    ("Latin America", r"s\.? ?a\.? indian|s\.? ?am\.? indian|south american|aztec|maya|inca|chibcha|chincha|carib|mexic|argentin|chile|brazil|peru|bolivia|colombia|venezuel|guiana|toba|chiriguano|cashinawa|tupinamba|warrau|yuracare|paressi|chamacoco|guarani|caingang|bacairi|chaco|tembe|mataco|araucan|tarascan|zapotec|quich|mosquito|cuna|jivaro|tukano|guaray|tenetehara|yamana|ona\b|bororo|kaingang|apinaye|sherente|munduruc|puerto ric|cuba|dominic|central america|nicaragua|panama|honduras|guatemal|costa rica|salvador|uruguay|paraguay|ecuador"),
    ("North America", r"n\.? ?a\.? indian|n\.? ?am\.? indian|north american indian|calif|western mono|ojibwa|chippewa|pawnee|navaho|navajo|cherokee|seneca|tahltan|kaska|quileute|zu[nñ]i|pueblo|iroquois|micmac|menomini|klikitat|american indian|plains|cree|blackfoot|crow|sioux|dakota|kiowa|apache|hopi|tlingit|haida|tsimshian|kwakiutl|bella coola|salish|chinook|thompson river|shoshon|\bute\b|paiute|arapaho|cheyenne|winnebago|fox\b|osage|wichita|caddo|creek|natchez|biloxi|seminole|choctaw|algonquin|maliseet|passamaquoddy|penobscot|montagnais|naskapi|athapask|nez perce|coeur|wishram|chilcotin|carrier|kathlamet|yurok|karok|hupa|maidu|pomo|wintu|yokuts|miwok|luiseno|mohave|diegue|pima|zuni|tewa|\bsia\b|acoma|laguna|cochiti|jicarilla|lipan|tonkawa|ponca|omaha|iowa|\boto\b|mandan|hidatsa|arikara|assiniboin|gros ventre|kutenai|okanagon|wasco|takelma|coos|tillamook|nootka|comox|lillooet|shuswap|kalispel|sanpoil|flathead|joshua|alsea|siuslaw"),
    ("Afro-Caribbean & North American folk", r"^u\.? ?s\.?$|\bu\. ?s\.|united states|missouri|american negro|am\.? negro|negro|jamaica|west indies|bahama|haiti|louisiana|creole|north carolina|new york|canad|virginia|kentucky|tennessee|ozark|pennsylvania|georgia\)|georgia|ohio|illinois|indiana|texas|maine|new england|massachusetts|appalach|antilles|martinique|guadeloupe|trinidad|barbados|grenada|virgin is|surinam|negro|nova scotia|newfoundland|acadian"),
]
REGION_RE = [(name, re.compile(rx, re.I)) for name, rx in REGIONS]

NOT_CULTURE = re.compile(
    r"^(answer|final formula|fable|cf|see|note|types?|example|e\.g|i\.e|ibid|for|literature|bibliography|"
    r"general|introduction|comment|motif|origin|tale|story|lit|ms|vol|no|nr|p|pp|tr|ed|chap|reference|refs?|"
    r"discussion|explanation|summary|sources?|versions?|cases|also)\b",
    re.I,
)

CANON = [
    (r"^icel(\.|andic)?$", "Icelandic"),
    (r"^irish( myth| saints?’? legend| romance)?$|^ireland$|^saints’ legend \(irish\)$", "Irish"),
    (r"^scot(ch|land|tish)$", "Scottish"),
    (r"^wales$|^welsh$", "Welsh"),
    (r"^esth?onian$", "Estonian"),
    (r"^missouri[- ]french$", "Missouri French"),
    (r"^french[- ]canadian$", "French Canadian"),
    (r"^easter is(\.|land)$", "Easter Island"),
    (r"^england$|^english$", "English"),
    (r"^hawaii(an)?$", "Hawaiian"),
    (r"^china$|^chinese$", "Chinese"),
    (r"^india$|^indian$", "India"),
    (r"^philippine$|^filipino$", "Philippine"),
    (r"^indonesian?$", "Indonesian"),
    (r"^african?$", "African"),
    (r"^am(\.|erican) negro$", "African American"),
    (r"^u\.? ?s\.?$|^united states$", "United States"),
    (r"^greek( myth)?$", "Greek"),
    (r"^hebrew$|^jewish$", "Jewish"),
    (r"^buddhist( myth)?$", "Buddhist"),
    (r"^lettish$|^latvian$", "Latvian"),
    (r"^polynesian?$", "Polynesian"),
    (r"^melanesian?$", "Melanesian"),
    (r"^rumanian$", "Romanian"),
]
CANON_RE = [(re.compile(rx, re.I), name) for rx, name in CANON]

GROUP_PREFIX = re.compile(
    r"^(african american|africa|african|n\.? ?a\.? indian|n\.? ?am\.? indian|north american indian|calif\.? indian|"
    r"s\.? ?a\.? indian|s\.? ?am\.? indian|so\.? am\.? indian|south american indian|eskimo|american indian|"
    r"philippine|am\.? negro|american negro|india|papua|melanesia)\s*\((.+)\)$",
    re.I,
)
# a people named under one of these groups belongs to its region, whatever its name
# resembles elsewhere ("Africa (Baluba)" is not Oceania's Alu)
GROUP_REGIONS = {
    "Africa": "Africa", "North American Indian": "North America", "South American Indian": "Latin America",
    "Eskimo": "Arctic", "African American": "Afro-Caribbean & North American folk",
    "Philippine": "Oceania", "Papua": "Oceania", "Melanesia": "Oceania", "India": "South Asia",
}
GROUP_NAMES = {
    "africa": "Africa", "african": "Africa", "eskimo": "Eskimo", "philippine": "Philippine",
    "india": "India", "papua": "Papua", "melanesia": "Melanesia",
}


def group_name(prefix: str) -> str:
    p = prefix.lower().replace(" ", "").replace(".", "")
    if p.startswith(("na", "nam", "northamerican", "calif", "americanindian")):
        return "North American Indian"
    if p.startswith(("sa", "sam", "soam", "southamerican")):
        return "South American Indian"
    if "negro" in p:
        return "African American"
    return GROUP_NAMES.get(prefix.lower(), prefix.title())


def canon_culture(label: str):
    """Map a raw reference label to (tradition, region) or None."""
    label = re.sub(r"\s+", " ", label.strip(" *([.,")).strip()
    # the end of the previous sentence can cling to a label: "Odin.) Icelandic", "“…once.” Finnish"
    m = re.match(r"^[^(]*?[)”?!]\s+(.+)$", label)
    if m:
        label = m.group(1)
    if label.endswith(")") and "(" not in label:
        label = label[:-1].strip()
    if not label or len(label) > 60 or NOT_CULTURE.match(label):
        return None
    if re.search(r"\d", label):
        return None
    m = GROUP_PREFIX.match(label)
    if m:
        group = group_name(m.group(1))
        people = m.group(2).split(",")[0].strip()
        tradition = f"{group} ({people})" if people else group
        if group in GROUP_REGIONS:
            # Thompson's "North American Indian" sometimes names Mexican or Caribbean peoples
            if group == "North American Indian" and dict(REGION_RE)["Latin America"].search(people):
                return tradition, "Latin America"
            return tradition, GROUP_REGIONS[group]
        region_probe = group + " " + people
    else:
        tradition = label
        for rx, name in CANON_RE:
            if rx.match(label):
                tradition = name
                break
        if re.match(r"^(n\.? ?a\.?|n\.? ?am\.?|calif\.?) indian$", label, re.I):
            tradition = "North American Indian"
        elif re.match(r"^(s\.? ?a\.?|s\.? ?am\.?|so\.? am\.?) indian$", label, re.I):
            tradition = "South American Indian"
        region_probe = label + " " + tradition
    for name, rx in REGION_RE:
        if rx.search(region_probe):
            return tradition, name
    return None


SEG_SPLIT = re.compile(r"[;—]|(?<!\b[A-Z])(?<!\bAm)(?<!\bSo)(?<!\bNo)(?<!\bIs)(?<!\bCf)\.\s+(?=\*?[A-Z][a-z][^:;]{0,45}:)")
LABEL_RE = re.compile(r"^\s*\(?\*?([A-Z][^:\d]{1,55}?)\s*:")


def cultures_of(refs: str):
    found = []
    for seg in SEG_SPLIT.split(refs):
        m = LABEL_RE.match(seg)
        if not m:
            continue
        label = m.group(1)
        parts = [label] if GROUP_PREFIX.match(label.strip(" *")) else re.split(r",\s*|\s+and\s+", label)
        for part in parts:
            c = canon_culture(part)
            if c and c not in found:
                found.append(c)
    return found


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------


def load_index_entries():
    """Headings and ranges from the old MOMFER index (covers A and B)."""
    sections, heads = [], []
    for line in open(ROOT / "data" / "raw" / "tmi-index.txt", encoding="utf-8"):
        line = line.strip()
        m = re.match(r"^([A-Z]\d+)\.-([A-Z]\d+)\.\s*(.+)$", line)
        if m:
            sections.append({"lo": m.group(1), "hi": m.group(2), "title": m.group(3)})
            continue
        m = re.match(r"^([A-Z]\d+)\.\s*(.+)$", line)
        if m:
            heads.append({"id": m.group(1), "title": m.group(2)})
    return sections, heads


def main():
    motifs = json.load(open(BUILD / "motifs.raw.json"))
    meta = json.load(open(BUILD / "sections.json"))
    categories = meta["categories"]
    for m in motifs:
        if m["id"] in PATCHES:
            m.update(PATCHES[m["id"]])
        m["title"] = re.sub(r"(?<=[a-z])\.\d$", ".", m["title"])
        if not re.search(r"[.?!][\"”’)]*$", m["title"]):
            m["title"] = m["title"].rstrip(" ,;:") + "."
    by_id = {m["id"]: m for m in motifs}

    old_sections, old_heads = load_index_entries()
    sections = {}
    for s in meta["sections"] + old_sections:
        key = (s["lo"], s["hi"])
        if s["lo"][0] != s["hi"][0] or num(s["lo"]) > num(s["hi"]):
            continue
        if key not in sections:
            sections[key] = {"lo": s["lo"], "hi": s["hi"], "title": tidy_heading(s["title"])}
    # group heads: synopsis headings that are themselves motifs
    group_heads = set()
    for h in meta["headings"] + old_heads:
        hid = h["id"]
        if "." not in hid and hid in by_id:
            group_heads.add(hid)
    for s in sections.values():
        if s["lo"] in by_id:
            group_heads.add(s["lo"])

    nodes = {}  # id -> node dict (sections + motifs + categories)
    for L, name in categories.items():
        nodes[L] = {"id": L, "kind": "category", "title": name, "parent": None}
    for (lo, hi), s in sections.items():
        sid = f"{lo}–{hi}"
        nodes[sid] = {"id": sid, "kind": "section", "title": s["title"], "lo": num(lo), "hi": num(hi),
                      "letter": lo[0], "parent": None}

    # section nesting: smallest strictly-containing range
    by_letter = defaultdict(list)
    for sid, n in nodes.items():
        if n["kind"] == "section":
            by_letter[n["letter"]].append(n)
    for L, secs in by_letter.items():
        for s in secs:
            best = None
            for t in secs:
                if t is s:
                    continue
                if t["lo"] <= s["lo"] and s["hi"] <= t["hi"] and (t["lo"], t["hi"]) != (s["lo"], s["hi"]):
                    if best is None or (t["hi"] - t["lo"]) < (best["hi"] - best["lo"]):
                        best = t
            s["parent"] = best["id"] if best else L

    def innermost_section(mid):
        L, k = letter(mid), num(mid)
        best = None
        for s in by_letter.get(L, []):
            if s["lo"] <= k <= s["hi"]:
                if best is None or (s["hi"] - s["lo"]) < (best["hi"] - best["lo"]):
                    best = s
        return best

    heads_by_letter = defaultdict(list)
    for h in group_heads:
        heads_by_letter[letter(h)].append(num(h))
    for L in heads_by_letter:
        heads_by_letter[L].sort()

    for m in motifs:
        mid = m["id"]
        node = {"id": mid, "kind": "motif", "parent": None}
        nodes[mid] = node
        if "." in mid:
            parts = mid.split(".")
            parent = None
            for i in range(len(parts) - 1, 0, -1):
                cand = ".".join(parts[:i])
                if cand in by_id:
                    parent = cand
                    break
            node["parent"] = parent
            if parent:
                continue
        sec = innermost_section(mid)
        base = re.match(r"[A-Z]\d+", mid).group(0)
        k = num(base)
        if base != mid and base not in by_id:
            # dotted motif whose base number is missing: attach as if it were the base
            pass
        if mid not in group_heads or base != mid:
            hs = heads_by_letter.get(letter(mid), [])
            i = bisect_right(hs, k) - 1
            if i >= 0:
                g = f"{letter(mid)}{hs[i]}"
                if g != mid and (sec is None or hs[i] >= sec["lo"]):
                    node["parent"] = g
                    continue
        node["parent"] = sec["id"] if sec else letter(mid)

    # sections that merely repeat their parent section (the old index and the
    # synopsis sometimes give overlapping ranges with the same heading) are dissolved
    def norm(t):
        return re.sub(r"[^a-z]", "", t.lower())

    redundant = {nid for nid, n in nodes.items() if n["kind"] == "section" and n["parent"]
                 and nodes[n["parent"]]["kind"] == "section" and norm(n["title"]) == norm(nodes[n["parent"]]["title"])}
    for n in nodes.values():
        while n["parent"] in redundant:
            n["parent"] = nodes[n["parent"]]["parent"]
    for nid in redundant:
        del nodes[nid]
    print(f"dissolved {len(redundant)} redundant sections", file=sys.stderr)

    # but we keep sections as browse structure; children lists:
    children = defaultdict(list)
    for nid, n in nodes.items():
        if n["parent"]:
            children[n["parent"]].append(nid)

    def sort_key(nid):
        n = nodes[nid]
        if n["kind"] == "section":
            return (n["lo"], -1, -(n["hi"] - n["lo"]), [])
        parts = nid.split(".")
        return (num(parts[0]), 0, 0, [int(p) for p in parts[1:] if p.isdigit()])

    for p in children:
        children[p].sort(key=sort_key)

    # ancestors
    def ancestors(nid):
        out = []
        p = nodes[nid]["parent"]
        while p:
            out.append(p)
            p = nodes[p]["parent"]
        return out

    # enrich motifs
    culture_counts = Counter()
    region_counts = Counter()
    type_counts = Counter()
    for m in motifs:
        n = nodes[m["id"]]
        cul = cultures_of(m["refs"])
        m["cultures"] = [c for c, _ in cul]
        m["regions"] = sorted({r for _, r in cul})
        culture_counts.update(m["cultures"])
        region_counts.update(m["regions"])
        type_counts.update(m["types"])
        m["cf"] = [c for c in dict.fromkeys(m["cf"]) if c in by_id and c != m["id"]]

    # back-links for cross references
    cited_by = defaultdict(list)
    for m in motifs:
        for c in m["cf"]:
            cited_by[c].append(m["id"])

    def node_title(nid):
        n = nodes[nid]
        if n["kind"] == "motif":
            return by_id[nid]["title"].rstrip(".")
        return n["title"]

    out_nodes = []
    for nid, n in nodes.items():
        rec = {"id": nid, "kind": n["kind"], "parent": n["parent"], "children": children.get(nid, [])}
        if n["kind"] == "motif":
            m = by_id[nid]
            rec.update({k: m[k] for k in ("title", "note", "refs", "cf", "types", "cultures", "regions")})
            rec["cited_by"] = cited_by.get(nid, [])
            if "alt_titles" in m:
                rec["alt_titles"] = m["alt_titles"]
        else:
            rec["title"] = n["title"]
        anc = ancestors(nid)
        rec["path"] = anc[::-1]
        rec["depth"] = len(anc)
        out_nodes.append(rec)

    # embedding text: headline + note + the chain of nearest ancestor titles
    for rec in out_nodes:
        if rec["kind"] != "motif":
            continue
        chain = [node_title(a) for a in rec["path"] if nodes[a]["kind"] != "category"]
        ctx = " › ".join(chain[-3:])
        text = rec["title"]
        if rec["note"]:
            text += " " + rec["note"]
        rec["context"] = ctx
        rec["category"] = categories[rec["id"][0]]

    order = {nid: i for i, nid in enumerate(sorted(nodes, key=lambda x: (x[0], sort_key(x) if nodes[x]["kind"] != "category" else (-1, -2, 0, []))))}
    out_nodes.sort(key=lambda r: order[r["id"]])

    json.dump({"categories": categories, "nodes": out_nodes,
               "cultures": culture_counts.most_common(), "regions": region_counts.most_common(),
               "types": type_counts.most_common()},
              open(BUILD / "tmi.json", "w"), ensure_ascii=False)

    n_motifs = sum(1 for r in out_nodes if r["kind"] == "motif")
    n_sections = sum(1 for r in out_nodes if r["kind"] == "section")
    print(f"{n_motifs} motifs, {n_sections} sections, {len(culture_counts)} traditions, "
          f"{len(region_counts)} regions, {len(type_counts)} tale types", file=sys.stderr)
    with_cult = sum(1 for m in motifs if m["cultures"])
    print(f"motifs with a tradition: {with_cult}", file=sys.stderr)
    print(region_counts.most_common(), file=sys.stderr)


if __name__ == "__main__":
    main()

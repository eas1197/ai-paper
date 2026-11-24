"""C16 conservative candidate identity grouping; no eligibility decision."""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

ROOT = Path(__file__).resolve().parents[3]


def _original():
    path = str(ROOT / "04_议题文献与现实/v012_第12版/tools")
    if path not in sys.path:
        sys.path.insert(0, path)
    from native_library import registry
    registry()
    from abstract_acquisition import clean_doi
    from collect_common import normalize
    from verified_identity import resolve, MATCH
    from codex_literature import web_url
    return clean_doi, normalize, resolve, MATCH, web_url


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def canonical_report_url(raw):
    """Conservative URL normalization; do not erase content-selecting parameters."""
    if not isinstance(raw, str):
        return None
    try:
        parsed = urlsplit(raw)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None
        port = parsed.port
    except ValueError:
        return None
    host = parsed.hostname.lower()
    if ":" in host:
        host = "[" + host + "]"
    netloc = host + (":" + str(port) if port and port != 443 else "")
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not k.lower().startswith("utm_")]
    # Preserve parameter order: repeated or signed query parameters can be meaningful.
    return urlunsplit(("https", netloc, parsed.path or "/", urlencode(query), ""))


def _bibliography(row):
    year = row.get("publication_date") or ""
    return {"title": row.get("title") or "", "journal": row.get("publication") or "",
            "authors": row.get("authors") or [], "year": year[:4] if re.match(r"^\d{4}", year) else "",
            "doi": row.get("doi") or ""}


def group_sources(rows, *, reviewed_report_aliases=None):
    """Return candidate groups and conflict quarantine, preserving every observation.

    reviewed_report_aliases maps normalized URL to a common report identity, ONLY
    when independently reviewed by the caller (not a model claim). It is not
    an authentication mechanism. Unreviewed equal titles/events never merge.
    """
    clean_doi, normalize, resolve, matches, web_url = _original()
    aliases = reviewed_report_aliases or {}
    if any(canonical_report_url(k) != k or not isinstance(v, str) or not v.strip()
           for k, v in aliases.items()):
        raise ValueError("Invalid reviewed report alias mapping")
    descriptors = []
    for row in rows:
        kind = row["source_type"]
        bib = _bibliography(row) if kind == "literature" else None
        url = canonical_report_url(row.get("original_url"))
        doi = clean_doi(bib["doi"]) if bib else None
        descriptor = {"kind": kind, "url": url, "doi": doi, "bib": bib}
        descriptors.append(descriptor)
    parent = list(range(len(rows)))
    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    def union(i, j):
        parent[root(j)] = root(i)
    bad = set()
    conflicts = []
    def quarantine(i, j, reason):
        bad.update((i, j))
        conflicts.append({"indexes": [i, j], "reason": reason})
    for i, a in enumerate(descriptors):
        for j in range(i + 1, len(rows)):
            b = descriptors[j]
            if a["kind"] != b["kind"]:
                continue
            if a["kind"] == "literature":
                x, y = a["bib"], b["bib"]
                same_doi = bool(a["doi"] and a["doi"] == b["doi"])
                same_title = (x["journal"] and x["journal"] == y["journal"]
                              and x["year"] and x["year"] == y["year"]
                              and normalize(x["title"]) and normalize(x["title"]) == normalize(y["title"]))
                if not (same_doi or same_title):
                    continue
                decision = resolve(x, y)
                if decision in matches:
                    union(i, j)
                elif same_doi or decision == "doi_conflict":
                    quarantine(i, j, decision)
            elif a["url"] and b["url"]:
                same_url = a["url"] == b["url"]
                same_alias = a["url"] in aliases and b["url"] in aliases and aliases[a["url"]] == aliases[b["url"]]
                if same_url or same_alias:
                    union(i, j)
    components = {}
    for i in range(len(rows)):
        components.setdefault(root(i), []).append(i)
    groups = []
    for indexes in components.values():
        first = descriptors[indexes[0]]
        if first["kind"] == "literature":
            for pos, i in enumerate(indexes):
                for j in indexes[pos+1:]:
                    if resolve(descriptors[i]["bib"], descriptors[j]["bib"]) not in matches:
                        quarantine(i, j, "ambiguous_bridge")
        if bad.intersection(indexes):
            for i in indexes:
                bad.add(i)
            continue
        if first["kind"] == "literature":
            dois = sorted({descriptors[i]["doi"] for i in indexes if descriptors[i]["doi"]})
            if dois:
                key = ["literature", "doi", dois[0]]
            else:
                # Complete identity only; incomplete metadata never yields an automatic merge.
                biblio = [descriptors[i]["bib"] for i in indexes]
                keys = [[normalize(b["journal"]), normalize(b["title"]), b["year"],
                         sorted(normalize(n) for n in b["authors"])] for b in biblio]
                key = ["literature", "bibliography", sorted(keys)[-1]]
                if not all(keys[0]):
                    key = ["literature", "unresolved", rows[indexes[0]]]
        elif first["url"]:
            key = [first["kind"], "report_alias", aliases[first["url"]]] if first["url"] in aliases else [first["kind"], "url", first["url"]]
        else:
            key = [first["kind"], "unresolved", rows[indexes[0]]]
        groups.append({"source_identity": "S_" + _digest(key), "candidate_key": key,
                       "members": [{"index": i, "record": rows[i]} for i in indexes],
                       "formal_eligible": False})
    return {"groups": groups, "conflicts": conflicts,
            "quarantined": [{"index": i, "record": rows[i]} for i in sorted(bad)],
            "note": "Candidate identity only; original receivers retain academic authority. Same event never proves same report or independence."}

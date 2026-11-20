"""Read-only imports and injectable reasoning/PDF interfaces. No API credentials."""
from __future__ import annotations

import csv
import html
import json
import re
import sqlite3
import unicodedata
import uuid
from contextlib import closing
from pathlib import Path
from typing import Protocol

from runtime import load, sha, value_hash


class LiteratureProvider(Protocol):
    def read(self, specification: dict) -> list[dict]: ...


class ModelProvider(Protocol):
    """Implementations receive only supplied literature/context, never survey microdata."""
    provider_id: str
    model_version: str

    def propose(self, task: dict) -> dict: ...


def text(value):
    return html.unescape(re.sub(r"<[^>]*>", "", str(value or ""))).strip()


def norm(value):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", text(value)).casefold())


def doi(value):
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text(value).casefold()).rstrip(".")


class LocalLiteratureProvider:
    def read(self, spec):
        path = Path(spec["path"])
        fmt = spec.get("format", path.suffix.lower().lstrip("."))
        if fmt == "json":
            raw = load(path)
            rows = raw if isinstance(raw, list) else raw["papers"]
        elif fmt == "csv":
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
        elif fmt == "ris":
            rows = self.ris(path.read_text(encoding="utf-8-sig"))
        elif fmt == "zotero":
            rows = self.zotero(path)
        else:
            raise ValueError(f"不支持的本地格式: {fmt}")
        result = []
        for row in rows:
            authors = row.get("authors", [])
            if isinstance(authors, str):
                authors = json.loads(authors) if authors.startswith("[") else [a.strip() for a in re.split(r"[;；]", authors) if a.strip()]
            record = {"title": text(row.get("title")), "authors": authors,
                      "year": str(row.get("year") or "")[:4] or None,
                      "journal": text(row.get("journal")), "doi": doi(row.get("doi")) or None,
                      "abstract": text(row.get("abstract")) or None,
                      "url": row.get("url"), "source_id": spec["source_id"],
                      "search_id": row.get("search_id") if fmt != "zotero" else None,
                      "origin": spec.get("origin") if fmt != "zotero" else "local",
                      "source_record_id": str(row.get("source_record_id") or "") or None,
                      "access_basis": spec["access_basis"], "share_scope": spec.get("share_scope", "local_only"),
                      "retrieved_at": spec["retrieved_at"], "metadata_sha256": sha(path),
                      "metadata_origin_path": str(path),
                      "original_paper_id": row.get("paper_id"), "fulltext_source_path": row.get("fulltext_path"),
                      "abstract_read_at": None, "fulltext_read_at": None,
                      "acquisition_status": "abstract_available" if text(row.get("abstract")) else "metadata_found"}
            if not record["title"]:
                raise ValueError("题录标题不能为空")
            if record["fulltext_source_path"]:
                record["fulltext_source_path"] = str((path.parent / record["fulltext_source_path"]).resolve())
            result.append(record)
        return result

    @staticmethod
    def ris(raw):
        rows, current, last = [], {}, None
        for line in raw.splitlines():
            match = re.match(r"^([A-Z0-9]{2})  - ?(.*)$", line)
            if match:
                tag, val = match.groups()
                if tag == "TY":
                    if current:
                        raise ValueError("RIS记录缺少ER终止符")
                    current = {}
                elif tag == "ER":
                    if current:
                        rows.append({"title": (current.get("TI") or current.get("T1") or [""])[0],
                                     "authors": current.get("AU", current.get("A1", [])),
                                     "year": (current.get("PY") or current.get("Y1") or [""])[0],
                                     "journal": (current.get("JO") or current.get("JF") or current.get("T2") or [""])[0],
                                     "doi": (current.get("DO") or [""])[0],
                                     "abstract": "\n".join(current.get("AB", current.get("N2", []))),
                                     "url": (current.get("UR") or [None])[0],
                                     "source_record_id": (current.get("ID") or [None])[0]})
                    current, last = {}, None
                else:
                    current.setdefault(tag, []).append(val)
                    last = tag
            elif line.strip() and last:
                current[last][-1] += "\n" + line.strip()
        if current:
            raise ValueError("RIS末条记录未结束；拒绝静默丢弃")
        return rows

    @staticmethod
    def zotero(path):
        # A normal live Zotero database may be locked; propagate error for normal export.
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            fields = {}
            for item, name, value in db.execute("SELECT d.itemID,f.fieldName,v.value FROM itemData d JOIN fields f ON d.fieldID=f.fieldID JOIN itemDataValues v ON d.valueID=v.valueID"):
                fields.setdefault(item, {})[name] = value
            rows = []
            for item, key in db.execute("SELECT i.itemID,i.key FROM items i JOIN itemTypes t ON i.itemTypeID=t.itemTypeID WHERE t.typeName='journalArticle' AND i.itemID NOT IN (SELECT itemID FROM deletedItems)"):
                f = fields.get(item, {})
                authors = ["".join((a or "", b or "")) for a, b in db.execute("""
                    SELECT c.lastName,c.firstName FROM itemCreators ic
                    JOIN creators c ON ic.creatorID=c.creatorID
                    JOIN creatorTypes ct ON ct.creatorTypeID=ic.creatorTypeID
                    WHERE ic.itemID=? AND ct.creatorType='author' ORDER BY ic.orderIndex
                """, (item,))]
                attachments = []
                for attachment_key, attachment_path in db.execute("SELECT i.key,a.path FROM itemAttachments a JOIN items i ON a.itemID=i.itemID WHERE a.parentItemID=?", (item,)):
                    if attachment_path and attachment_path.startswith("storage:"):
                        candidate = path.parent / "storage" / attachment_key / attachment_path[8:]
                        if candidate.suffix.lower() == ".pdf" and candidate.is_file():
                            attachments.append(str(candidate))
                rows.append({"title": f.get("title"), "authors": authors, "year": f.get("date"),
                             "journal": f.get("publicationTitle"), "doi": f.get("DOI"),
                             "abstract": f.get("abstractNote"), "url": f.get("url"),
                             "source_record_id": key, "fulltext_path": attachments[0] if attachments else None})
            return rows


def deduplicate(records, catalog=None):
    """Transitive union over identifiers; conflicting DOI/fingerprint matches are quarantined."""
    catalog = catalog if catalog is not None else {}
    parent = list(range(len(records)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    keys = {}
    for i, r in enumerate(records):
        candidates = []
        if r.get("doi"):
            candidates.append(("doi", doi(r["doi"])))
        if r.get("source_record_id"):
            candidates.append(("source", r["source_id"], r["source_record_id"]))
        if r.get("authors") and r.get("year"):
            candidates.append(("fingerprint", norm(r["title"]), tuple(sorted(norm(a) for a in r["authors"])), r["year"]))
        for key in candidates:
            if key in keys:
                parent[find(i)] = find(keys[key])
            else:
                keys[key] = i
    groups = {}
    for i, r in enumerate(records):
        groups.setdefault(find(i), []).append(r)
    papers, conflicts = [], []
    for group in groups.values():
        ids = sorted({r["doi"] for r in group if r.get("doi")})
        fingerprints = {(norm(r["title"]), tuple(sorted(norm(a) for a in r["authors"])), r["year"]) for r in group}
        conflict = len(ids) > 1 or (len(fingerprints) > 1 and len({norm(r["title"]) for r in group}) > 1)
        # Prefer explicit persistent IDs from an export; otherwise derive one from the
        # strongest available identity. Retain alias IDs when sources are merged.
        supplied = sorted({r["original_paper_id"] for r in group if r.get("original_paper_id")})
        strong = ("doi", ids[0]) if ids else min(("source", r["source_id"], r["source_record_id"]) for r in group if r.get("source_record_id")) if any(r.get("source_record_id") for r in group) else ("bibliographic", sorted(fingerprints, key=str)[0])
        identity_keys = []
        for r in group:
            if r.get("doi"):
                identity_keys.append(value_hash(["doi", r["doi"]]))
            if r.get("source_record_id"):
                identity_keys.append(value_hash(["source", r["source_id"], r["source_record_id"]]))
            if r.get("authors") and r.get("year"):
                identity_keys.append(value_hash(["bibliographic", norm(r["title"]), sorted(norm(a) for a in r["authors"]), r["year"]]))
        previous = sorted({catalog[k] for k in identity_keys if k in catalog})
        generated = "P_" + (value_hash(strong)[:20] if strong[0] in ("doi", "source") else uuid.uuid4().hex[:20])
        identity = previous[0] if previous else supplied[0] if supplied else generated
        supplied = sorted(set(supplied + previous))
        for k in identity_keys:
            catalog[k] = identity
        chosen = dict(max(group, key=lambda r: (bool(r.get("abstract")),
                                               r.get("origin") == "online_search",
                                               bool(r.get("fulltext_source_path")))))
        chosen.update(paper_id=identity, aliases=[x for x in supplied if x != identity], provenance=group, identity_status="conflict" if conflict else "unverified")
        chosen["identity_keys"] = {"dois": ids, "sources": [[r["source_id"], r.get("source_record_id")] for r in group]}
        if conflict:
            conflicts.append({"paper_id": identity, "reason": "标识或题录冲突，需人工拆分/核对", "records": group})
        papers.append(chosen)
    if len({r["paper_id"] for r in papers}) != len(papers):
        raise ValueError("同一paper_id被用于不同文献")
    return sorted(papers, key=lambda r: r["paper_id"]), conflicts


class PdfReader:
    def inspect(self, path):
        if Path(path).read_bytes()[:5] != b"%PDF-":
            raise ValueError("不是PDF：可能是登录页或下载未完成")
        try:
            import pdfplumber
        except ImportError as exc:
            raise ValueError("PDF解析需要pdfplumber；缺依赖时保留缺口，不计全文取得") from exc
        try:
            with pdfplumber.open(path) as doc:
                pages = [page.extract_text() or "" for page in doc.pages]
        except Exception as exc:
            raise ValueError(f"PDF无法解析: {type(exc).__name__}: {exc}") from exc
        if not pages:
            raise ValueError("PDF无页面")
        return pages

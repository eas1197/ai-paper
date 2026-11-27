"""One identity rule for source verification and final grouping."""

from abstract_acquisition import build_articles, clean_doi
from collect_common import digest, normalize
from multi_acquisition import author_keys, author_names, canonical_journal


MATCH = {"doi", "bibliographic", "linked_detail"}


def resolve(left, right, *, linked=False):
    journal = canonical_journal(left)
    a, b = clean_doi(left.get("doi")), clean_doi(right.get("doi"))
    title, other = normalize(left.get("title")), normalize(right.get("title"))
    first, second = author_keys(left), author_keys(right)
    years = [str(row.get("year") or "") for row in (left, right)]
    if not title or not other or not journal or journal != canonical_journal(right):
        return "different_journal_or_missing_identity"
    if a and b and a != b:
        return "doi_conflict"
    if all(years) and years[0] != years[1]:
        return "year_conflict"
    if first and second and first != second:
        shorter, longer = sorted((first, second), key=len)
        if len(shorter) != 1 or not shorter < longer:
            return "author_conflict"
    if title != other and not (
        a and a == b and first & second
        and (title.startswith(other) or other.startswith(title))
    ):
        return "doi_title_conflict" if a and a == b else "title_unconfirmed"
    if a and a == b and first & second and all(years):
        return "doi"
    if first & second and all(years):
        return "bibliographic"
    if linked and second and years[1]:
        return "linked_detail"
    return "author_year_unconfirmed"


def group_verified(observations, groups):
    rows = [r for r in observations if r["status"] == "valid_abstract"]
    by_doi, by_title = {}, {}
    for index, row in enumerate(rows):
        doi = clean_doi(row.get("doi"))
        if doi:
            by_doi.setdefault(doi, []).append(index)
        by_title.setdefault(
            (row["journal"], normalize(row["title"]), str(row.get("year"))), []
        ).append(index)

    pairs = {}
    for doi_bucket in (*by_doi.values(), *by_title.values()):
        for pos, i in enumerate(doi_bucket):
            for j in doi_bucket[pos + 1:]:
                pairs[i, j] = resolve(rows[i], rows[j])

    parent = list(range(len(rows)))

    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i

    bad = set()
    conflicts = []

    def quarantine(i, j, why):
        bad.update((i, j))
        conflicts.append({
            "reason": why,
            "observations": [
                {k: rows[n].get(k) for k in ("provider", "url", "doi", "year", "authors")}
                for n in (i, j)
            ],
        })

    for (i, j), why in pairs.items():
        a, b = rows[i], rows[j]
        doi = clean_doi(a.get("doi"))
        if why in MATCH:
            parent[root(j)] = root(i)
        elif (doi and doi == clean_doi(b.get("doi"))) or (
            why == "doi_conflict" and bool(author_keys(a) & author_keys(b))
        ):
            quarantine(i, j, why)
    components = {}
    for i in range(len(rows)):
        components.setdefault(root(i), []).append(i)
    articles = []
    for indexes in components.values():
        for pos, i in enumerate(indexes):
            for j in indexes[pos + 1:]:
                why = pairs.get((i, j))
                if why is None:
                    why = resolve(rows[i], rows[j])
                if why not in MATCH and i not in bad and j not in bad:
                    quarantine(i, j, "ambiguous_bridge:" + why)
        if bad.intersection(indexes):
            continue
        members = [rows[i] for i in indexes]
        exemplar = max(members, key=lambda r: (len(author_names(r)), len(r["title"])))
        projection = [
            dict(row, title=exemplar["title"], authors=author_names(exemplar))
            for row in members
        ]
        result, _ = build_articles(projection, groups)
        identity = result[0].get("doi") or [
            exemplar["journal"], normalize(exemplar["title"]), str(exemplar["year"]),
            sorted(author_keys(exemplar)),
        ]
        result[0]["article_id"] = "A_" + digest(identity)[:24]
        articles.extend(result)
    return articles, conflicts

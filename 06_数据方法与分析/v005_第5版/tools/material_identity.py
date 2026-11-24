"""F10: conservative qualitative source/event identity observations, not adjudication."""
from source_identity import canonical_report_url


def identity_candidates(materials):
    """Keep report identity separate from alleged social event identity.

    Identical URLs may discuss distinct events; different URLs may be reprints.
    Model claims and matching context never certify event independence.
    """
    reports, claims, locators, pending = {}, {}, {}, []
    for row in materials:
        mid=row["material_id"]
        url=canonical_report_url(row.get("url"))
        if url:
            reports.setdefault(url,[]).append(mid)
            locators.setdefault((url,row["locator"]),[]).append(mid)
        identity=row.get("event_identity_claim")
        if isinstance(identity,str) and identity.strip() and identity.strip().lower()!="unknown":
            claims.setdefault(identity.strip(),[]).append(mid)
        else:
            pending.append(mid)
    return {"same_report_candidates":[{"url":url,"material_ids":ids} for url,ids in reports.items() if len(ids)>1],
        "same_locator_candidates":[{"url":url,"locator":loc,"material_ids":ids} for (url,loc),ids in locators.items() if len(ids)>1],
        "same_claimed_event_candidates":[{"claimed_identity":key,"material_ids":ids} for key,ids in claims.items() if len(ids)>1],
        "missing_event_identity":pending,
        "cross_report_reprints_or_distinct_events":"pending_independent_review",
        "independent_event_count":None,"formal_eligible":False}

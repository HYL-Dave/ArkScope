"""Compare independent per-run artifacts, never accumulated database counts."""
from collections import Counter
import json
import sys


def compare(old, new):
    reasons = []
    for field in ("article_id", "mode", "scope", "source_hash", "provider_count", "capture_profile"):
        if old.get(field) != new.get(field):
            reasons.append(field + "_changed")
    if old.get("strategy") != "observe" or new.get("strategy") != "guarded":
        reasons.append("strategies_invalid")
    if old.get("document_key") == new.get("document_key"):
        reasons.append("same_document_already_expanded")
    if old.get("provider_count") is None:
        reasons.append("provider_count_unknown")
    if reasons:
        return {"status":"inconclusive", "reasons":reasons}
    if any(item.get("status") != "captured" for item in (old, new)):
        return {"status":"not_accepted", "reasons":["capture_failed"]}
    if old["provider_count"] > 0 and any(not item.get("comments") for item in (old, new)):
        return {"status":"inconclusive", "reasons":["positive_count_without_captured_comments"]}
    if old.get("detail", {}).get("body_markdown") != new.get("detail", {}).get("body_markdown"):
        return {"status":"inconclusive", "reasons":["article_body_changed"]}

    def signatures(comments):
        def text(row):
            return tuple(row.get(key) for key in ("commenter", "comment_date", "comment_text"))
        by_id = {}
        for row in comments:
            by_id.setdefault(row["comment_id"], []).append(text(row))
        result = []
        for row in comments:
            parent_id = row.get("parent_comment_id")
            parents = by_id.get(parent_id, []) if parent_id else []
            if parent_id and len(parents) != 1:
                raise ValueError("parent_identity_unresolved")
            result.append((text(row), parents[0] if parents else None))
        return Counter(result)

    try:
        left, right = signatures(old["comments"]), signatures(new["comments"])
    except (ValueError, KeyError):
        return {"status":"inconclusive", "reasons":["comment_identity_unresolved"]}
    missing = sum((left - right).values())
    added = sum((right - left).values())
    if missing:
        return {"status":"not_accepted", "reasons":["comments_missing_or_changed"],"missing":missing,"added":added}
    if added:
        reasons.append("new_comments_or_different_coverage")
    if new.get("scroll", {}).get("controls_unresolved"):
        reasons.append("unrecognized_controls")
    if new.get("mode") == "backfill" and (
        new["scroll"].get("stop_reason") != "stable_bottom"
        or new["scroll"].get("stable_bottom_rounds", 0) < 5
    ):
        reasons.append("initial_scan_not_terminal")
    if any(round_.get("audit", {}).get("omitted_count", 0) for capture in (old, new)
           for round_ in capture.get("scroll", {}).get("control_audits", [])):
        reasons.append("candidate_trace_truncated")
    for field in ("rounds", "elapsed_ms"):
        if new["scroll"][field] > old["scroll"][field]:
            reasons.append(field + "_increased")
    return {"status":"inconclusive" if reasons else "no_regression_observed",
            "reasons":reasons,"missing":missing,"added":added}


if __name__ == "__main__":
    with open(sys.argv[1]) as before, open(sys.argv[2]) as after:
        print(json.dumps(compare(json.load(before), json.load(after)), indent=2))

"""Bind resource observations to their Markdown, not to a completeness claim."""

import hashlib
import json


def validate_capture(value: object) -> dict | None:
    if value is None:
        return None
    keys = {"schema_version", "extractor_version", "links", "images", "unsupported_embeds"}
    if (type(value) is not dict or set(value) != keys
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or type(value["extractor_version"]) is not int or value["extractor_version"] != 2):
        raise ValueError("sa_article_body_capture_invalid")
    for name in ("links", "images"):
        counts = value[name]
        if (type(counts) is not dict or set(counts) != {"observed", "retained"}
                or any(type(v) is not int or not 0 <= v <= 10_000 for v in counts.values())
                or counts["retained"] > counts["observed"]):
            raise ValueError("sa_article_body_capture_invalid")
    if type(value["unsupported_embeds"]) is not int or not 0 <= value["unsupported_embeds"] <= 10_000:
        raise ValueError("sa_article_body_capture_invalid")
    return value


def encode_capture(body: str, capture: object) -> str | None:
    capture = validate_capture(capture)
    if capture is None:
        return None
    return json.dumps({"body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                       "capture": capture}, sort_keys=True, separators=(",", ":"))


def reference_coverage(body: str | None, stored: str | None) -> dict:
    """Reading never fetches image bytes or infers a clean DOM from old text."""
    if stored is None:
        return {"status": "not_recorded", "image_storage": "unknown"}
    try:
        if not isinstance(stored, str) or len(stored) > 4096:
            raise ValueError("invalid capture envelope")
        value = json.loads(stored)
        if (type(value) is not dict or set(value) != {"body_sha256", "capture"}
                or value["body_sha256"] != hashlib.sha256((body or "").encode("utf-8")).hexdigest()):
            raise ValueError("capture/body mismatch")
        capture = validate_capture(value["capture"])
        if capture is None:
            raise ValueError("missing capture")
    except (ValueError, TypeError, RecursionError):
        return {"status": "unavailable", "reason_code": "sa_article_body_capture_invalid",
                "image_storage": "unknown"}
    gaps = (capture["unsupported_embeds"]
            + sum(capture[name]["observed"] - capture[name]["retained"] for name in ("links", "images")))
    return {"status": "partial" if gaps else "observed_references_retained",
            "basis": "selected_article_dom", "extractor_version": capture["extractor_version"],
            "image_storage": "remote_references_only", "links": capture["links"],
            "images": capture["images"], "unsupported_embeds": capture["unsupported_embeds"]}

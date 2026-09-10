"""Read-only explanations bound to a transition, never today's route or findings."""

from datetime import date
import hashlib
import json
from urllib.parse import parse_qsl, urlsplit

from src.lifecycle_public_sources import SourceReadError, canonical_source_url
from src.lifecycle_web_schema import WebJournalError
from src.lifecycle_journal_codec import digest_json
from src.security_lifecycle_investigation import (
    SecurityLifecycleInvestigationStore, assessment_fingerprint, observation_fingerprint,
)
from src.security_lifecycle_provider_snapshot import decode_snapshot, instant
from src.security_lifecycle_review import confirmation_for
from src.ticker_identity_transition import profile_snapshot_sha256


_PROVIDERS = {"massive_reference": "Massive", "massive_ticker_events": "Massive",
              "eodhd_symbol_directory": "EODHD", "nasdaq_symbol_directory": "Nasdaq"}


def _text(value, *, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError("history_text")
    return value


def _time(value):
    return None if value is None else instant(value).isoformat().replace("+00:00", "Z")


def _day(value):
    if value is not None and (not isinstance(value, str) or date.fromisoformat(value).isoformat() != value):
        raise ValueError("history_date")
    return value


def _strings(value):
    if not isinstance(value, list):
        raise ValueError("history_list")
    return [_text(item, required=True) for item in value]


def _link(value, gaps):
    if value is None:
        return None
    try:
        url = canonical_source_url(value)
        if any(any(part in key.lower() for part in ("token", "key", "secret", "signature", "credential", "authorization"))
               for key, _ in parse_qsl(urlsplit(url).query)):
            raise SourceReadError("unsafe_source_url")
        return url
    except SourceReadError:
        gaps.append("source_link_omitted")
        return None


def _source(*, gaps, name=None, url=None, title=None, published_at=None, observed_at=None,
            kind="document", ticker=None, listing_status=None, market=None):
    url = _link(url, gaps)
    if listing_status not in {None, "active", "inactive", "not_found", "unverified"}:
        raise ValueError("history_listing_status")
    return {"name": _text(name) or (urlsplit(url).hostname if url else None), "url": url,
            "title": _text(title), "published_at": _text(published_at), "observed_at": _time(observed_at),
            "kind": kind, "ticker": _text(ticker), "listing_status": listing_status, "market": _text(market)}


def _evidence_source(row, gaps):
    locator = row.get("source_locator")
    if locator is None and row.get("source_locator_json") is not None:
        locator = json.loads(row["source_locator_json"])
    locator = {} if locator is None else locator
    if not isinstance(locator, dict):
        raise ValueError("history_source_locator")
    listing = row.get("kind") == "listing_directory_snapshot"
    return _source(gaps=gaps, name=_PROVIDERS.get(row.get("adapter")) or row.get("publisher") or row.get("domain"),
        url=row.get("source_url"), title=row.get("title"), published_at=row.get("source_published_at"),
        observed_at=row.get("retrieved_at"), kind="listing_snapshot" if listing else
        "ticker_events" if row.get("kind") == "ticker_event_snapshot" else "manual" if row.get("adapter") == "manual" else "document",
        ticker=locator.get("candidate_ticker") if listing else None,
        listing_status=locator.get("listing_status") if listing else None, market=locator.get("market") if listing else None)


def _provider_check(conn, transition, packet):
    if packet is not None:
        digest = packet.get("provider_check_sha256")
        candidates = conn.execute("SELECT * FROM security_lifecycle_provider_checks WHERE content_sha256=? AND ticker=?",
                                  (digest, transition["source_ticker"]))
    else:
        # Old approvals pin an observation fingerprint, not the check ID. Search
        # small envelopes only; newer observations are never substituted.
        candidates = conn.execute("SELECT check_id,observation_json FROM security_lifecycle_provider_checks WHERE ticker=? ORDER BY rowid DESC",
                                  (transition["source_ticker"],))
    for candidate in candidates:
        if packet is None:
            try:
                envelope = json.loads(candidate["observation_json"])
                if not isinstance(envelope, dict):
                    continue
                observation = envelope["observation"] if "snapshot_format" in envelope else envelope
                if not isinstance(observation, dict):
                    continue
                if observation_fingerprint(observation) != transition["approved_observation_fingerprint_sha256"]:
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            candidate = conn.execute("SELECT * FROM security_lifecycle_provider_checks WHERE check_id=?", (candidate["check_id"],)).fetchone()
        checked = decode_snapshot(candidate)
        if (observation_fingerprint(checked["observation"]) != transition["approved_observation_fingerprint_sha256"]
                or instant(checked["at"]) > instant(transition["approved_at"])):
            raise ValueError("history_observation_binding")
        return checked
    return None


def _bound_json(encoded, digest):
    value = json.loads(encoded)
    if digest_json(value) != digest or not isinstance(value, dict):
        raise ValueError("history_journal_binding")
    return value


def _model(value):
    provider, auth = value["provider"], value["auth_mode"]
    if (provider, auth) not in {("openai", "api_key"), ("openai", "chatgpt_oauth"),
                               ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")}:
        raise ValueError("history_execution")
    # A historical model may be retired now. Do not consult today's registry.
    return {"provider": provider, "auth_mode": auth, "model": _text(value["model"], required=True)}


def _web_passages(conn, web, citations):
    # The approval pins SourcePassage digests, including URL and capture time.
    # Locate the bound quotations inside SQLite without loading full documents
    # into Python or rerunning today's finding/model validation.
    passages = []
    for citation in citations:
        quote = _text(citation["quote"], required=True)
        page = conn.execute("""
            WITH source AS (
                SELECT page_json,json_extract(page_json,'$.text') AS body
                FROM lifecycle_web_pages WHERE run_id=? AND source_id=? AND json_valid(page_json)
            ), located AS (SELECT *,instr(body,?) AS position FROM source)
            SELECT json_extract(page_json,'$.url') AS source_url,
                   json_extract(page_json,'$.body_sha256') AS source_document_sha256,
                   json_extract(page_json,'$.text_sha256') AS source_text_sha256,
                   json_extract(page_json,'$.retrieved_at') AS retrieved_at,
                   position,length(CAST(substr(body,1,position-1) AS BLOB)) AS start_byte,
                   instr(substr(body,position+1),?) AS duplicate_quote
            FROM located
            """, (web["run_id"], citation["source_id"], quote, quote)).fetchone()
        if page is None or page["position"] is None or page["position"] <= 0 or page["duplicate_quote"]:
            return []
        passages.append({key: page[key] for key in ("source_url", "source_document_sha256", "source_text_sha256", "retrieved_at", "start_byte")})
        passages[-1].update(end_byte=page["start_byte"] + len(quote.encode()), excerpt=quote,
                            cited_text_sha256=hashlib.sha256(quote.encode()).hexdigest())
    return passages if digest_json(passages) == web["passages_sha256"] else []


def _llm(conn, transition, packet, result):
    target = packet["lane"] == "investigation"
    if target:
        from src.lifecycle_investigation.schema import verify_journal
        verify_journal(conn)
        jobs, results, calls = "lifecycle_investigation_jobs", "lifecycle_investigation_results", "lifecycle_investigation_calls"
        result_hash = "payload_sha256"
    else:
        from src.lifecycle_web_schema import verify_web_journal
        verify_web_journal(conn)
        jobs, results, calls = "lifecycle_web_runs", "lifecycle_web_results", "lifecycle_web_calls"
        result_hash = "result_sha256"
    web = packet["web"]
    run = conn.execute(f"SELECT header_json,header_sha256,status,finished_at FROM {jobs} WHERE run_id=?", (web["run_id"],)).fetchone()
    saved = conn.execute(f"SELECT payload_json,{result_hash} FROM {results} WHERE run_id=?", (web["run_id"],)).fetchone()
    if run is None or saved is None:
        raise ValueError("history_journal_missing")
    header = _bound_json(run["header_json"], web["header_sha256"])
    material = _bound_json(saved["payload_json"], web["result_sha256"])
    selected = _model(header["selection"])
    completed = conn.execute(f"SELECT terminal,remote_id FROM {calls} WHERE run_id=?", (web["run_id"],)).fetchall()
    if (run["status"] != "succeeded" or run["header_sha256"] != web["header_sha256"] or saved[result_hash] != web["result_sha256"]
            or selected != _model(web["execution"]) or not completed
            or any(row["terminal"] != "completed" or not row["remote_id"] for row in completed)
            or instant(run["finished_at"]) > instant(transition["approved_at"])):
        raise ValueError("history_execution_binding")
    finding = material["validated"]["finding"] if target else material["finding"]
    if (finding["source_ticker"] != transition["source_ticker"] or finding.get("successor_ticker") != transition["successor_ticker"]
            or finding["effective_date"] != packet["finding"]["effective_date"]):
        raise ValueError("history_finding_binding")
    result.update(method="llm_investigation", model=selected, summary=_text(finding["summary"], required=True),
                  observed_at=_time(run["finished_at"]), limitations=_strings(finding.get("limitations", [])))
    if target:
        passages = material["validated"]["passages"]
        if digest_json(passages) != web["passages_sha256"]:
            raise ValueError("history_passage_binding")
        for passage in passages:
            result["sources"].append(_source(gaps=result["gaps"], name=passage["publisher"], url=passage["url"], title=passage["title"],
                published_at=passage["published_at"], observed_at=passage["retrieved_at"],
                kind="document" if passage["corpus"] == "web" else "local_news"))
    else:
        for passage in _web_passages(conn, web, finding["citations"]):
            result["sources"].append(_source(gaps=result["gaps"], url=passage["source_url"], observed_at=passage["retrieved_at"]))
    result["source_gaps"] = [{"url": _link(gap["url"], result["gaps"]), "reason": _text(gap["reason"], required=True)}
                             for gap in packet.get("source_gaps", [])]


def _empty(transition, gap):
    return {"summary": None, "impact": None, "method": "unknown", "approval_authority": transition["approval_authority"],
            "event_date": None, "observed_at": None, "model": None, "sources": [], "limitations": [], "source_gaps": [], "gaps": [gap]}


def project_decision(conn, transition):
    """Missing/corrupt explanatory material cannot erase an applied receipt."""
    try:
        preview = transition["approved_preview"]
        if (not isinstance(preview, dict) or profile_snapshot_sha256(preview) != transition["approved_preview_sha256"]
                or preview["assessment_id"] != transition["assessment_id"] or preview["case_id"] != transition["case_id"]
                or preview["source_ticker"] != transition["source_ticker"] or preview["successor_ticker"] != transition["successor_ticker"]):
            raise ValueError("history_approval_binding")
        packet = confirmation_for(transition)["packet"] if "review_confirmation" in preview else None
        store = SecurityLifecycleInvestigationStore(conn)
        if packet is None:
            try:
                finding = store.get_assessment(transition["assessment_id"])
            except KeyError:
                return _empty(transition, "assessment_missing")
            if (finding["case_id"] != transition["case_id"] or assessment_fingerprint(finding) != transition["approved_assessment_fingerprint_sha256"]
                    or finding["observation_fingerprint_sha256"] != transition["approved_observation_fingerprint_sha256"]
                    or finding["evidence_set_sha256"] != preview["evidence_set_sha256"]):
                raise ValueError("history_assessment_binding")
            provenance = finding
        else:
            finding = packet["finding"]
            provenance = packet.get("provenance", {})
        result = {**_empty(transition, ""), "summary": _text(finding["conclusion"], required=True),
                  "impact": _text(finding["impact_summary"], required=True), "event_date": _day(finding["effective_date"]), "gaps": []}
        if packet is None:
            # Legacy fingerprints bind IDs and evidence, not the assessment's
            # prose/date/provenance. Do not imply that those fields were sealed.
            result["gaps"].append("legacy_assessment_unsealed")
        if packet is not None and packet.get("lane") in {"web", "investigation"}:
            _llm(conn, transition, packet, result)
        else:
            method = provenance.get("automation_method")
            result["method"] = "rule_engine" if method == "deterministic_rule" else "llm_investigation" if method == "model_assisted" else "manual_review"
            if method == "model_assisted":
                result["gaps"].append("model_missing")
            case = store.get_case_identity(transition["case_id"])
            if case["source"] == "listing_authority":
                if method is None:
                    result["method"] = "provider_review"
                checked = _provider_check(conn, transition, packet)
                if checked is None:
                    result["gaps"].append("sources_missing")
                else:
                    result["sources"] = [_evidence_source(row, result["gaps"]) for row in checked["evidence"]]
                    result["observed_at"] = _time(checked["at"])
                    result["limitations"] = [_text(checked["observation"]["description"], required=True)]
            references = packet["source_references"] if packet is not None else []
            if packet is None:
                for citation in finding["citations"]:
                    if citation["reference_kind"] != "evidence":
                        continue
                    row = store.get_evidence(citation["evidence_id"])
                    if (row["case_id"] != transition["case_id"] or row["content_sha256"] != citation["cited_content_sha256"]
                            or hashlib.sha256(row["excerpt"].encode()).hexdigest() != citation["cited_content_sha256"]):
                        raise ValueError("history_citation_binding")
                    references.append(row)
            result["sources"].extend(_evidence_source(row, result["gaps"]) for row in references)
        result["sources"] = list({json.dumps(row, sort_keys=True): row for row in result["sources"]}.values())
        if not result["sources"]:
            result["gaps"].append("sources_missing")
        result["gaps"] = sorted(set(result["gaps"]))
        return result
    except (KeyError, TypeError, ValueError, WebJournalError):
        return _empty(transition, "record_invalid")

#!/usr/bin/env python3
"""
Provenance Guard — the web service.

    python app.py

Then, in another terminal:

    curl -X POST http://127.0.0.1:5000/ping \
      -H "Content-Type: application/json" \
      -d '{"message": "hello"}'

That's the example route. It works right now, before you've written anything.
**Leave it alone** — it's your control. When something breaks later, check that
`/ping` still answers: if it does, the problem is in your handler; if it
doesn't, it's the service itself.

Routes:

    POST /ping        the worked example. Already works. Don't edit it
    POST /submit      ← YOU BUILD THIS (Milestone 3, 4, 5)
    POST /appeal      ← YOU BUILD THIS (Milestone 5)
    GET  /log         the audit log. Already works
    GET  /health      is the service up, and is the model loaded
"""

import uuid

from flask import Flask, jsonify, request

import audit
import config
import scoring
import stylometry

app = Flask(__name__)


# ── Rate limiting — UNIT 8 ────────────────────────────────────────────────────
# Off until you turn it on. In unit 8, Milestone 1:
#
#   1. Set RATE_LIMITING_ENABLED = True in config.py (or AI201_RATE_LIMITS=1)
#   2. Choose your numbers there
#   3. Uncomment the @limiter.limit(...) line on /submit below
#
# The order doesn't matter. While limiting is off, that decorator is a no-op
# that quietly does nothing, so uncommenting it early costs you nothing — but
# it also means no 429 until you've done step 1.
#
# The storage backend is preconfigured, which stops Flask-Limiter printing a
# warning on every start. In-memory is right for one laptop and wrong for
# anything real — a restart forgets every count.

class _LimiterOff:
    """
    Stands in for the real limiter while rate limiting is off.

    It makes @limiter.limit(...) a decorator that returns the route
    untouched, so uncommenting the line before you flip the setting is
    harmless instead of a crash on startup.
    """

    def limit(self, *args, **kwargs):
        return lambda view: view


limiter = _LimiterOff()
if config.RATE_LIMITING_ENABLED:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    def rate_limit_key():
        """
        Who a request counts against.

        Falling back to the caller's address is the easy version. Unit 8's
        stretch asks about per-creator limits instead — and the difference
        matters: one script can look like a thousand callers, and one household
        can look like one.
        """
        payload = request.get_json(silent=True)
        # A body that parses as JSON but isn't an object — a bare list or
        # string — has no .get. Without this guard the key function raises
        # BEFORE the route runs, and a malformed request becomes a 500 that
        # looks like your handler crashed when your handler never ran.
        if not isinstance(payload, dict):
            return get_remote_address()
        creator = payload.get("creator_id")
        return creator if isinstance(creator, str) and creator.strip() else get_remote_address()

    limiter = Limiter(
        key_func=rate_limit_key,
        app=app,
        storage_uri=config.RATE_LIMIT_STORAGE,
        default_limits=[],
    )

    @app.errorhandler(429)
    def rate_limited(exc):
        """
        A rejected request still leaves a trace.

        ⚠️ An attack that shows up only as an absence is one you'll never find.
        """
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            payload = {}
        audit.log_rejection(
            creator_id=payload.get("creator_id", "unknown"),
            reason="rate_limited",
            limit=str(exc.description),
        )
        return jsonify({
            "error": "rate_limited",
            "message": "Too many submissions. Try again shortly.",
            "limit": str(exc.description),
        }), 429


# ── The worked example. Already works. Don't edit. ────────────────────────────

@app.post("/ping")
def ping():
    """
    Everything a route needs, in six lines.

    JSON arrives as a dict. You pull things out of it. You return a dict and
    the framework turns it into a response. That's the whole idea.
    """
    payload = request.get_json(silent=True) or {}
    return jsonify({
        "ok": True,
        "you_sent": payload.get("message"),
        "service": "provenance-guard",
    })


@app.get("/health")
def health():
    """Is the service up, and has the model been downloaded yet?"""
    import detector

    loaded = detector._model is not None
    return jsonify({
        "ok": True,
        "detector_model": config.DETECTOR_MODEL,
        "detector_loaded": loaded,
        "rate_limiting": config.RATE_LIMITING_ENABLED,
        "log_entries": len(audit.read_entries()),
    })


# ── YOU BUILD THIS ────────────────────────────────────────────────────────────

MAX_TEXT_CHARS = 20_000


def _error(status: int, code: str, message: str, creator_id=None):
    """A clean JSON refusal that also leaves a trace in the audit log."""
    audit.log_rejection(
        creator_id=creator_id if isinstance(creator_id, str) else "unknown",
        reason=code,
    )
    return jsonify({"error": code, "message": message}), status


@app.post("/submit")
# @limiter.limit(f"{config.RATE_LIMIT_PER_MINUTE}/minute;{config.RATE_LIMIT_PER_DAY}/day")
def submit():
    """
    Take a piece of text, decide about it, log the decision, answer.

    In:   {"text": "...", "creator_id": "..."}
    Out:  {"content_id", "guess", "confidence", "label",
           "model_score", "style_score", "combined_score", "status"}

    Pipeline: validate -> signal one -> signal two -> combine -> label -> log.
    Every refusal is a 4xx JSON error (never a 500) and is logged too.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error(400, "invalid_json", "Send a JSON object with 'text' and 'creator_id'.")

    text = payload.get("text")
    creator_id = payload.get("creator_id")

    if not isinstance(creator_id, str) or not creator_id.strip():
        return _error(400, "missing_creator_id", "'creator_id' must be a non-empty string.")
    if not isinstance(text, str):
        return _error(400, "missing_text", "'text' must be a string.", creator_id)
    if not text.strip():
        return _error(400, "empty_text", "'text' is empty.", creator_id)
    if len(text) > MAX_TEXT_CHARS:
        return _error(
            413, "text_too_long",
            f"'text' is {len(text):,} characters; the limit is {MAX_TEXT_CHARS:,}.",
            creator_id,
        )
    if len(stylometry.words(text)) < 5:
        return _error(400, "text_too_short", "Please submit at least a few sentences.", creator_id)

    import detector  # imported here so /ping and /health never wait on the model

    try:
        model_score = detector.model_signal(text)
    except detector.DetectorUnavailable as exc:
        return _error(503, "detector_unavailable", str(exc).splitlines()[0], creator_id)
    except ValueError as exc:
        return _error(400, "text_too_short", str(exc), creator_id)

    style_score = stylometry.style_signal(text)
    combined = scoring.combine_signals(model_score, style_score)
    guess, label = scoring.score_to_label(combined)
    confidence = scoring.confidence(combined)

    content_id = uuid.uuid4().hex[:12]
    audit.log_decision(
        content_id=content_id,
        creator_id=creator_id,
        guess=guess,
        model_score=model_score,
        style_score=style_score,
        combined_score=combined,
        label=label,
        status="decided",
        confidence=confidence,
    )

    return jsonify({
        "content_id": content_id,
        "guess": guess,
        "confidence": confidence,
        "label": label,
        "model_score": model_score,
        "style_score": style_score,
        "combined_score": combined,
        "status": "decided",
    })


@app.post("/appeal")
def appeal():
    """
    A writer says we got it wrong.

    In:   {"content_id": "...", "reasoning": "..."}
    Out:  {"content_id", "status": "under_review", "message"}

    Only an id that exists can be appealed; anything else is a 4xx and writes
    nothing, so the log never holds an appeal against nothing.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error(400, "invalid_json", "Send a JSON object with 'content_id' and 'reasoning'.")

    content_id = payload.get("content_id")
    reasoning = payload.get("reasoning")

    if not isinstance(content_id, str) or not content_id.strip():
        return _error(400, "missing_content_id", "'content_id' must be a non-empty string.")
    if not isinstance(reasoning, str) or not reasoning.strip():
        return _error(400, "missing_reasoning", "Please tell us why you think this was wrong ('reasoning').")
    if len(reasoning) > 5_000:
        return _error(413, "reasoning_too_long", "Please keep your reasoning under 5,000 characters.")

    original = [e for e in audit.entries_for(content_id.strip()) if e.get("event") is None]
    if not original:
        audit.log_rejection(creator_id="unknown", reason="appeal_unknown_content_id", content_id=content_id[:64])
        return jsonify({
            "error": "unknown_content_id",
            "message": "We couldn't find a submission with that content_id. Check it and try again.",
        }), 404

    decision = original[0]
    audit.log_appeal(
        content_id=decision["content_id"],
        creator_id=decision["creator_id"],
        reasoning=reasoning.strip(),
    )
    return jsonify({
        "content_id": decision["content_id"],
        "status": "under_review",
        "message": "Thank you. We've recorded your appeal and a person will look at it. "
                   "Nothing has been decided against you in the meantime.",
    })


# ── Already works ─────────────────────────────────────────────────────────────

@app.get("/log")
def get_log():
    """
    The audit log, most recent last.

        curl "http://127.0.0.1:5000/log?limit=10"

    You need this in unit 8 to paste entries into your README, and you need it
    now to see whether your logging is actually working.
    """
    limit = request.args.get("limit", type=int)
    entries = audit.read_entries(limit=limit)
    return jsonify({"count": len(entries), "entries": entries})


def main():
    print(f"Provenance Guard on http://{config.HOST}:{config.PORT}")
    print(f"  detector model:  {config.DETECTOR_MODEL}")
    print(f"  rate limiting:   {'ON' if config.RATE_LIMITING_ENABLED else 'off (unit 8)'}")
    print(f"  audit log:       {config.AUDIT_LOG}")
    print()
    print("Check it's alive:")
    print(f'  curl -X POST http://{config.HOST}:{config.PORT}/ping \\')
    print('    -H "Content-Type: application/json" \\')
    print("    -d '{\"message\": \"hello\"}'")
    print()
    # debug=True hands out an interactive debugger, so it's local-only — see config.py
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)


if __name__ == "__main__":
    main()

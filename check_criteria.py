"""
Check the five acceptance criteria in criteria.md against the running service.

    python app.py            # terminal 1
    python check_criteria.py # terminal 2

Uses the same pieces as calibrate.py. Prints PASS/MISS per criterion.
"""

import json
import sys

import requests

import calibrate
import config
import scoring

BASE = f"http://{config.HOST}:{config.PORT}"


def post(path, body=None, raw=None):
    if raw is not None:
        return requests.post(BASE + path, data=raw, headers={"Content-Type": "application/json"}, timeout=120)
    return requests.post(BASE + path, json=body, timeout=120)


def submit(text, who="check"):
    r = post("/submit", {"text": text, "creator_id": who})
    r.raise_for_status()
    return r.json()


def main():
    S = calibrate.SAMPLES
    results = {}
    guesses = {}
    for group, texts in S.items():
        for i, t in enumerate(texts, 1):
            results[f"{group}-{i}"] = submit(t)
    ok_all = True

    # 1. false positives: 10 human pieces (5 human + 3 plain + 2 formal)
    humans = [results[f"{g}-{i}"] for g, n in (("human", 5), ("plain", 3), ("formal", 2)) for i in range(1, n + 1)]
    fp = sum(1 for r in humans if r["guess"] == "ai")
    c1 = fp <= 1
    print(f"[{'PASS' if c1 else 'MISS'}] 1. false positives: {fp} of {len(humans)} human pieces labeled AI (target <= 1)")

    # 2. spread
    ai = [results[f"ai-{i}"]["combined_score"] for i in range(1, 6)]
    hu = [results[f"human-{i}"]["combined_score"] for i in range(1, 6)]
    gap = sum(ai) / 5 - sum(hu) / 5
    worst_h = max(hu)
    c2 = gap >= 0.25 and worst_h <= 0.65
    print(f"[{'PASS' if c2 else 'MISS'}] 2. spread: mean AI - mean human = {gap:.3f} (target >= 0.25); highest clearly-human = {worst_h:.3f} (target <= 0.65)")

    # 3. label coverage
    seen = {r["guess"] for r in results.values()}
    sweep_bad = 0
    for k in range(0, 101):
        g, text = scoring.score_to_label(k / 100)
        if g not in ("ai", "human", "unsure") or not text:
            sweep_bad += 1
    c3 = seen == {"ai", "human", "unsure"} and sweep_bad == 0
    print(f"[{'PASS' if c3 else 'MISS'}] 3. labels reached in {len(results)} inputs: {sorted(seen)}; sweep gaps: {sweep_bad}")

    # 4. appeals
    ids = [results[k]["content_id"] for k in list(results)[:5]]
    good = 0
    for cid in ids:
        r = post("/appeal", {"content_id": cid, "reasoning": "I wrote this myself, from memory."})
        if r.status_code == 200 and r.json().get("status") == "under_review":
            good += 1
    log = requests.get(BASE + "/log").json()["entries"]
    logged = sum(1 for cid in ids if any(e.get("content_id") == cid and e.get("event") == "appeal" for e in log))
    before = len(log)
    bad = [post("/appeal", {"content_id": "nope", "reasoning": "x"}),
           post("/appeal", {"reasoning": "x"})]
    after = requests.get(BASE + "/log").json()["entries"]
    stray = sum(1 for e in after[before:] if e.get("event") == "appeal")
    c4 = good == 5 and logged == 5 and all(400 <= r.status_code < 500 for r in bad) and stray == 0
    print(f"[{'PASS' if c4 else 'MISS'}] 4. appeals: {good}/5 ok, {logged}/5 logged; bad ids -> {[r.status_code for r in bad]}, stray appeal entries: {stray}")

    # 5. bad input
    cases = {
        "missing text": dict(body={"creator_id": "c"}),
        "empty text": dict(body={"text": "", "creator_id": "c"}),
        "whitespace": dict(body={"text": "   \n\t ", "creator_id": "c"}),
        "number text": dict(body={"text": 12345, "creator_id": "c"}),
        "json list": dict(raw="[1, 2, 3]"),
        "missing creator": dict(body={"text": "Some words in a sentence here."}),
        "100k chars": dict(body={"text": "word " * 20000, "creator_id": "c"}),
    }
    codes = {}
    n_before = len(requests.get(BASE + "/log").json()["entries"])
    for name, kw in cases.items():
        r = post("/submit", **kw)
        codes[name] = r.status_code
    n_after = len(requests.get(BASE + "/log").json()["entries"])
    c5 = all(400 <= c < 500 for c in codes.values()) and (n_after - n_before) == len(cases)
    print(f"[{'PASS' if c5 else 'MISS'}] 5. bad input: {codes}; rejection entries logged: {n_after - n_before}/{len(cases)}")

    return 0 if all([c1, c2, c3, c4, c5]) else 1


if __name__ == "__main__":
    sys.exit(main())

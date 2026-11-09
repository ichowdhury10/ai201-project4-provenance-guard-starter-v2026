# Provenance Guard

> ### 👋 Start here
>
> **New to this repo? Read [RUNNING.md](RUNNING.md) first.**
>
> Once `python test.py` passes, in one terminal:
>
> ```bash
> python app.py
> ```
>
> and in another:
>
> ```bash
> curl -X POST http://127.0.0.1:5000/ping \
>   -H "Content-Type: application/json" \
>   -d '{"message": "hello"}'
> ```
>
> That's a web service. Something sent it text and it sent something back.
> Everything this unit is filling in the middle.
>
> **The rest of this file is your submission.** Fill it in as you go.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     Unit 7 asks for the first five sections. Unit 8 adds the five below.

     Everything is pasted as TEXT. A pasted curl response gets full credit;
     a picture of your terminal gets none.
     ───────────────────────────────────────────────────────────────────────── -->

<!-- ═══════════════════════ UNIT 7 — THE BUILD ═══════════════════════ -->

## What This Does

Provenance Guard is a small Flask service a writing site could plug into. A submission takes this path:

1. **Arrives** at `POST /submit` as `{"text", "creator_id"}`.
2. **Validation** (`app.py::submit`). Non-object bodies, a missing or non-string `text`, empty or whitespace text, text over 20,000 characters, and a missing `creator_id` are refused with a 4xx JSON error, and the refusal is logged. Accepted input gets a `content_id`.
3. **Signal one** (`detector.py::model_signal`) runs GPT-2 locally and returns `model_score`, how predictable the text is.
4. **Signal two** (`stylometry.py::style_signal`) measures the text's shape and returns `style_score`.
5. **Combine** (`scoring.py::combine_signals`) turns the two into one `combined_score`.
6. **Label** (`scoring.py::score_to_label`) maps that score to `ai`, `human` or `unsure` plus the sentence a reader sees. `confidence` is how far the score sits from the 0.5 coin-flip, scaled to 0–1.
7. **Log and answer** (`audit.py::log_decision`) appends one line to `logs/audit.jsonl` with all three scores, the guess, label and status `decided`, then returns the JSON. If the writer disagrees, `POST /appeal` finds the item by `content_id`, appends an appeal entry with their reasoning, and moves it to `under_review`. An unknown `content_id` is a 404 and writes nothing.

Planning notes from before I wrote any code are in [planning.md](planning.md). Acceptance criteria are in [criteria.md](criteria.md).

---

## Signals and Scoring

### Signal one — the model signal

**What it measures:** Perplexity under GPT-2 (`detector.py`, given with the starter, unchanged): how surprised a language model is by the text, squashed to 0–1 with higher meaning more AI-like.

**Why that might differ between human and AI writing:** A model writes by picking likely next words, so its output is low-surprise. People choose odd, specific words.

**What it can't see:** Who wrote it. It measures common words in ordinary sentences, and plenty of people write that way. In my calibration set, three plain human paragraphs scored 0.82–0.88 on this signal, the same as machine text (0.76–0.93). It is the signal most likely to wrongly accuse a plain writer.

### Signal two — the style signal

**What it measures:** `stylometry.py::style_signal`, the text as shape and not meaning. Four parts, each rescaled to 0–1 where 1 is AI-like, then combined with weights:

| Part | Measure | Weight |
|---|---|---|
| spread | variation of sentence length (stdev / mean, in words). Even sentences score AI-like | 0.35 |
| ttr | unique words / total, averaged over 50-word windows. Narrow vocabulary scores AI-like | 0.15 |
| punct | amount and variety of non-final punctuation (`, ; : — ( " ! ?` and so on). Little and uniform scores AI-like | 0.30 |
| length | average sentence length. Chatbot prose averages 14+ words; under about 8 scores human | 0.20 |

Texts under 20 words are pulled toward 0.5, because a few numbers from a few words are mostly noise.

**Why that might differ between human and AI writing:** Generated prose tends toward even, mid-length sentences, tidy punctuation and a narrow vocabulary. Human writing is lumpier.

**What it can't see:** Meaning. Anyone can move the shape without changing the author: add typos, chop or merge sentences, paste in a quote, add dashes. Short texts give noisy numbers. Some disciplined human styles (legal, technical) are uniform by training. I added the `length` part after calibration showed plain human writing scoring AI-like on every other part, which means it is tuned partly to my own sample, and an AI asked to write in short plain sentences would walk straight through it.

### The combining rule

**The rule:** Take the average of the two scores. If the two signals are more than 0.25 apart, pull that average halfway back toward 0.5, because two methods disagreeing is itself uncertainty and should read as "unsure" instead of an accusation resting on one signal. Then the thresholds decide the label. The AI line is set high on purpose, so the false-positive decision lives there as much as in the weights.

**The numbers** (all in `config.py`):

- weights: model 0.5, style 0.5
- disagreement: gap > 0.25, shrink 0.5
- thresholds: score <= 0.35 is human, score >= 0.80 is AI, anything between is unsure

**Where it lives:** `scoring.py::combine_signals`

**A case where my two signals split, and what my rule does with it:** My own paragraph about a grandmother's button jar (the calibration piece `human-1`) scored `model_score` 0.622 (GPT-2 found the plain opening predictable) and `style_score` 0.347 (uneven sentences, lots of punctuation). The gap of 0.275 triggers the rule, the average 0.485 is pulled to 0.492, and the writer gets "unsure" instead of leaning either way.

**What calibration showed** (`python calibrate.py`, 17 pieces I chose by hand; the whole set is in `calibrate.py`):

| Group | mean model | mean style | mean combined |
|---|---|---|---|
| clearly AI (5) | 0.844 | 0.645 | 0.702 |
| clearly human (5) | 0.417 | 0.209 | 0.344 |
| plain human (3) | 0.856 | 0.633 | 0.705 |
| formal human (2) | 0.422 | 0.407 | 0.414 |
| lightly edited AI (2) | 0.522 | 0.417 | 0.469 |

The honest reading: the two signals separate clear AI from clear human well (0.358 apart) but **neither can separate plain human writing from AI**. Plain human pieces combine to 0.62–0.78, inside the range of the AI pieces (0.59–0.81). No weighting fixes that, so I moved the AI line up to 0.80 so none of the plain pieces gets accused. The price is that only 1 of my 5 clear-AI pieces reaches the AI label; the other 4 are "unsure". I chose that trade because a wrong accusation costs a writer more than a missed detection costs the site. I set both thresholds by looking at the same 17 pieces I then tested on, so the passing results below are not a held-out test, and the next unit's attack set is the real one.

---

## Label Variants

| Label | Score range | The exact text a reader sees |
|---|---|---|
| high-confidence human | 0.00 – 0.35 | We think this was probably written by a person. |
| unsure | 0.35 – 0.80 | We can't tell how this was written. Our checks didn't point clearly either way, so we're not drawing a conclusion. Nothing is held against you, and you don't need to do anything. |
| high-confidence AI | 0.80 – 1.00 | Our checks found patterns in this text that are common in AI-written text, but they can't prove it, and plain, simple writing by people can look this way too. If you wrote this yourself, please tell us. You can appeal, and a person will look at it. |

**Why I worded the "unsure" one this way:** The person reading it may well have written every word themselves, so it says what happened (our checks didn't point either way) before it says anything about them, says outright that nothing is held against them, and asks for nothing. It never uses "AI" or "suspicious". The AI label is hedged for the same reason: it says "patterns", admits plain human writing can look this way, and puts the appeal route in the label itself. I haven't yet had anyone else read these as a writer would. That test, from Milestone 5, is still open.

---

## Sample Run

**A submission.** This is a plain human paragraph, the kind this system is most likely to get wrong. Both signals call it AI-like (0.88 and 0.68) and it still lands in "unsure" because the combined score of 0.78 is under the 0.80 line.

```bash
$ curl -X POST http://127.0.0.1:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "I went to the store on Saturday. I bought milk, eggs, and bread. The store was very busy. I waited in line for a long time. Then I went home and made breakfast. My sister came over and we ate together. It was a good day. I like weekends because I can rest.", "creator_id": "writer-042"}'
```

```json
{
  "combined_score": 0.7809,
  "confidence": 0.5618,
  "content_id": "9c535cd7e6ff",
  "guess": "unsure",
  "label": "We can't tell how this was written. Our checks didn't point clearly either way, so we're not drawing a conclusion. Nothing is held against you, and you don't need to do anything.",
  "model_score": 0.8769,
  "status": "decided",
  "style_score": 0.6849
}
```

Note that `confidence` is 0.56 on an "unsure" guess. It measures how far the score is from the 0.5 coin-flip, not how sure the system is of that particular label, and that reads oddly beside the word "unsure". I left it and am flagging it as something to fix.

**An appeal**

```bash
$ curl -X POST http://127.0.0.1:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "9c535cd7e6ff", "reasoning": "I wrote this myself. I write in short sentences because English is my second language."}'
```

```json
{
  "content_id": "9c535cd7e6ff",
  "message": "Thank you. We've recorded your appeal and a person will look at it. Nothing has been decided against you in the meantime.",
  "status": "under_review"
}
```

**What the log shows afterwards**

```bash
$ curl "http://127.0.0.1:5000/log?limit=2"
```

```json
{
  "count": 2,
  "entries": [
    {
      "combined_score": 0.7809,
      "confidence": 0.5618,
      "content_id": "9c535cd7e6ff",
      "creator_id": "writer-042",
      "guess": "unsure",
      "label": "We can't tell how this was written. Our checks didn't point clearly either way, so we're not drawing a conclusion. Nothing is held against you, and you don't need to do anything.",
      "model_score": 0.8769,
      "status": "decided",
      "style_score": 0.6849,
      "timestamp": "2026-11-09T00:34:57+00:00"
    },
    {
      "content_id": "9c535cd7e6ff",
      "creator_id": "writer-042",
      "event": "appeal",
      "reasoning": "I wrote this myself. I write in short sentences because English is my second language.",
      "status": "under_review",
      "timestamp": "2026-11-09T00:34:57+00:00"
    }
  ]
}
```

**Checking my five criteria** (`python check_criteria.py`, output saved in `results/unit7_criteria_check.txt`):

```
[PASS] 1. false positives: 0 of 10 human pieces labeled AI (target <= 1)
[PASS] 2. spread: mean AI - mean human = 0.358 (target >= 0.25); highest clearly-human = 0.492 (target <= 0.65)
[PASS] 3. labels reached in 17 inputs: ['ai', 'human', 'unsure']; sweep gaps: 0
[PASS] 4. appeals: 5/5 ok, 5/5 logged; bad ids -> [404, 400], stray appeal entries: 0
[PASS] 5. bad input: {'missing text': 400, 'empty text': 400, 'whitespace': 400, 'number text': 400, 'json list': 400, 'missing creator': 400, '100k chars': 413}; rejection entries logged: 7/7
```

All five pass on one run. The model signal is almost deterministic on my machine, so I expect the same on repeats, but I only ran it once. These pieces are the same ones I calibrated on.

---

## How I Used AI

I built this with Claude Code, I used it to help me debug and analyze my code, so these are the two moments that changed what shipped.

**Moment 1**

- *What I asked for:* Implement `stylometry.py` with sentence-length spread, type-token ratio and punctuation density, combined into one score.
- *What came back:* A working signal, but when I ran it over my calibration pieces the three plain, short-sentence human paragraphs scored 0.85 on the model and 0.75+ on style, so they came out as clear AI.
- *What I changed:* I added a fourth part, average sentence length, to push very short sentences toward human. It lowered the plain pieces' style score from about 0.77 to 0.63 but did not fix them, so I stopped trying to separate them and moved the AI threshold to 0.80 instead. I wrote the limit into the README rather than hide it.

**Moment 2**

- *What I asked for:* A combining rule with a disagreement penalty.
- *What came back:* A shrink toward 0.5 when the signals are more than 0.25 apart.
- *What I changed:* On the calibration set it also pushed some clear-AI pieces (for example `ai-4`, 0.75 down to 0.63) and one human piece up into "unsure". I kept the rule because it behaves the same way in both directions and it matches the reasoning (disagreement is uncertainty), and I recorded that it costs AI recall.

<!-- ═══════════════════════ UNIT 8 — THE TEST ═══════════════════════ -->

---

## Rate Limiting

**My limits:** ___ per minute, ___ per day

**Why those numbers and not others:**
<!-- Think about two people: a real writer submitting their own work a few
     times an hour, and a script sending a thousand variations to map your
     thresholds. Your numbers have to be liveable for the first and hostile to
     the second. -->

**What a caller counts as:** <!-- per address, or per creator_id? They fail
differently — one script can look like a thousand callers, and one household
can look like one. -->

**The run of status codes when I pushed past it:**

<!-- python run_attacks.py --flood 15 -->

```

```

---

## Attack Run — Before

<!-- Every attack with its outcome and a held-or-broke mark.
     `run_attacks.py --label before` produces the table. -->



**Ten audit log entries from the run**

<!-- Choose entries that show the interesting failures, not the ten easiest. -->

```json

```

**The single worst outcome** — the one I'd least want to explain to a writer
whose work got caught by it:



---

## Run Log and Verdicts

<!-- Your five criteria across three trials. `run_eval.py --label before`. -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |
| 2.  |  |  |  |  |  |
| 3.  |  |  |  |  |  |
| 4.  |  |  |  |  |  |
| 5.  |  |  |  |  |  |

**Real output from one trial**, pasted as text, naming the file and function
that produced it:

```json

```

**Diagnoses**

<!-- For each miss AND each broken attack: the stage and the mechanism.

     Your service has five stages: the route, signal one, signal two, the
     combining rule, and the label mapping.

     Not a diagnosis:  "The evasion attacks got through."
     A diagnosis:      "Four evasion inputs got through. All four had typos
                        added to AI-generated text. My second signal measures
                        word variety, and typos raise word variety — so it read
                        them as more human. My combining rule weights that
                        signal at 0.6, so it dragged the whole score down."

     Look for a pattern. Five failures on one signal is one problem, not five. -->



---

## The Improvement

**What I changed:**

**Which diagnosis pointed at it:**

### Attack Run — After

<!-- Same format. `run_attacks.py --label after` -->



**Did it help, and how do I know:**

<!-- Widening the unsure band usually fixes one problem and creates another.
     Reporting that trade honestly is worth full credit. -->



---

## What's Still Broken

<!-- For each attack still getting through and each criterion still missed:
     what you'd do, and why you stopped. -->



**The trade I'd make if this ran for real:**

<!-- Two sentences. Fewer wrong accusations means more AI text getting through.
     Say which way you'd go and WHO PAYS FOR IT. -->



<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 7

       [ ] criteria.md has five numbered criteria, each naming a target
       [ ] Each has a reason underneath
       [ ] POST /submit returns content_id, guess, confidence, label,
           model_score and style_score
       [ ] Two signals that measure DIFFERENT things, each with a named blind spot
       [ ] Three label variants, all reachable, written out in full
       [ ] POST /appeal changes status and writes to the log
       [ ] Signals and Scoring names scoring.py::combine_signals
       [ ] Sample Run: a submission AND an appeal, as pasted text
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN

     SUBMISSION CHECKLIST — unit 8

       [ ] Rate limiting on /submit, with your numbers justified
       [ ] The pasted run of status codes showing 429
       [ ] Audit log with all nine fields, recording rejections too
       [ ] The attack set run IN FULL, every input with an outcome
       [ ] Ten audit log entries pasted as text
       [ ] Five criteria across three trials
       [ ] A diagnosis for every miss and every broken attack — stage AND mechanism
       [ ] One improvement, with Attack Run — After
       [ ] What's Still Broken, including the production trade
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**

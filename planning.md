# Planning — Milestone 1 (written before any code)

## The path a submission takes

1. **Arrives.** A client POSTs `{"text", "creator_id"}` to `/submit`.
2. **Validation (`app.py::submit`).** Body must be a JSON object; `text` a non-empty string, at most 20,000 characters; `creator_id` a non-empty string. Anything else is rejected with a 4xx JSON error and logged as a rejection. Adds: a `content_id` (uuid) once the input is accepted.
3. **Signal one (`detector.py::model_signal`).** A local GPT-2 measures how predictable the text is. Adds: `model_score` (0–1, higher = more AI-like).
4. **Signal two (`stylometry.py::style_signal`).** Measures sentence-length spread, vocabulary variety and punctuation variety. Adds: `style_score` (0–1, higher = more AI-like).
5. **Combine (`scoring.py::combine_signals`).** Turns the two scores into one `combined_score` (0–1), with a rule for disagreement.
6. **Label (`scoring.py::score_to_label`).** Maps the combined score to `ai` / `human` / `unsure` and the sentence a reader sees. Adds: `guess`, `label`, and the `confidence` shown to the caller.
7. **Log and answer (`audit.py::log_decision`).** One line is appended to `logs/audit.jsonl` (all three scores, guess, label, status `decided`), and the JSON response goes back. A later `/appeal` finds the item by `content_id` and moves it to `under_review`.

## The two signals

**Signal one — model predictability (perplexity under GPT-2).**
- Measures: how surprised a language model is by the text.
- Why it may differ: models write by choosing likely next words, so their output tends to be low-surprise. Humans pick odd, specific words.
- Can't see: authorship. Plain writing in common words (second-language writers, young writers, anyone writing simply) is also low-surprise, so it reads as machine. Ornate human prose reads as human; ornate AI prose also does.

**Signal two — style shape (`stylometry.py`).**
- Measures: the text as a shape. Spread of sentence lengths, type-token ratio, and how much and how varied the punctuation is.
- Why it may differ: AI prose tends to have even mid-length sentences and a narrow, tidy vocabulary and punctuation palette; human writing is lumpier.
- Can't see: meaning. Anyone can change the shape on purpose (typos, chopped or merged sentences, an inserted quote) without changing who wrote it. Short texts give noisy numbers. Some disciplined human styles (legal, technical, newswire) are uniform by training.

## Tracing the false positive

A real writer pastes a plain, short-sentence essay they wrote themselves. GPT-2 finds it predictable, so `model_score` is high (say 0.8). The sentences are even, so `style_score` is high too (say 0.7). The combined score is about 0.75, which the starter thresholds would call high-confidence AI. The writer would see an accusation, with no explanation and no numbers they could argue with.

What my design does about it:
- The high-confidence AI band is deliberately narrow (it sits high, at 0.72+), and the combining rule needs *both* signals to be high before the score can get there, so one confused signal can't make an accusation alone.
- The AI label is worded as "we can't rule out", not as a verdict, and it names the appeal route.
- `/appeal` takes the writer's reasoning, sets `under_review`, and writes it beside the original decision.

## Endpoint contracts

**POST /submit**
- In: `{"text": string (1–20000 chars), "creator_id": string}`
- Out 200: `{"content_id": str, "guess": "ai"|"human"|"unsure", "confidence": float 0–1, "label": str, "model_score": float, "style_score": float, "combined_score": float, "status": "decided"}`
- `confidence` is how sure the system is of its guess, i.e. distance from the middle of the scale: 0 at a score of 0.5, 1 at the extremes.
- Errors: 400 `{"error": code, "message": str}` for bad input, 413 for text over the limit, 503 if the model can't load.

**POST /appeal**
- In: `{"content_id": string, "reasoning": string (non-empty)}`
- Out 200: `{"content_id", "status": "under_review", "message": str}`
- Errors: 400 for missing fields, 404 for an unknown content_id (nothing is written).

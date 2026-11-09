# Acceptance criteria — Provenance Guard

Five criteria that say what "working" means for this service, written in unit 7
**before** you built it.

**All five are yours.** None are given.

An acceptance criterion names a number or something plainly observable. *"The
detector is accurate"* is an opinion — and perfect AI detection isn't possible
anyway, so it's an opinion about something nobody can deliver. *"Of 10 pieces I
wrote myself, at most 1 is labelled high-confidence AI"* is a criterion.

Under each, write a sentence or two on **why that target**. *"I allow at most 1
false positive in 10 because on a writing site a wrong accusation costs more
than a missed detection"* is a real answer.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

---

## Pick numbers you can defend

**Cover at least three of these five areas.** They're prompts, not a form.

| Area | A question it could answer |
|---|---|
| False positives | How often may a human's writing get called AI? |
| Score spread | How far apart should clearly-AI and clearly-human text score? |
| Label coverage | Is every one of your three labels actually reachable? |
| The appeal path | Does an appeal always change status and always get recorded? |
| Bad input | What happens when `text` is missing, empty, or enormous? |

Two things worth knowing before you pick numbers:

- **The expensive mistake is one-sided.** Missing some AI text costs the site a
  little. Accusing a real writer costs that person a lot. A criterion that
  treats both errors as equally bad is describing a system nobody would ship.
- **Unit 8 tests across three trials, and the target has to hold across all
  three.** Your first signal runs a model, so identical input can score
  differently twice. A target of "at most 1 in 10" against trials of 2, 1, 2 is
  a **miss**.

---
## 1. False positives: few real writers get accused

Of 10 pieces of human writing I judge to be real (including 3 deliberately plain, short-sentence pieces of the kind a second-language writer or a student might produce), **at most 1 is labeled high-confidence AI**, and this holds in each of three runs.

**Why this target:** On a writing site, a wrong accusation costs the writer far more than a missed detection costs the site. 1 in 10 is already a rate I would find hard to say out loud to the person it hits, so I'm not going higher. I'm including plain writing on purpose because that is where this kind of detector is weakest.

---

## 2. Score spread: AI and human text score clearly apart

The mean combined score of 5 clearly-AI pieces is **at least 0.25 higher** than the mean of 5 clearly-human pieces, and no clearly-human piece scores above 0.65.

**Why this target:** If the two groups sit within a few hundredths of each other, the score is noise dressed up as confidence. 0.25 is a quarter of the whole scale, enough to span the unsure band between the two labels.

---

## 3. Label coverage: all three labels are reachable and there are no gaps

Across a set of 15 varied inputs, **all three labels (AI, human, unsure) each appear at least once**, and a sweep of every score from 0.00 to 1.00 in steps of 0.01 maps to exactly one of the three labels (0 gaps, 0 overlaps).

**Why this target:** A label nobody can ever receive is dead text, and a gap in the ranges would crash or return nothing for some real score. The sweep is a plain, checkable fact. The 15-input check makes sure the labels are reachable by real text rather than only in theory.

---

## 4. The appeal path always works and never invents records

For **5 of 5** appeals sent with a valid content_id, the response is 200 with status `under_review`, and `GET /log` shows a new appeal entry with that content_id and the writer's reasoning. For **2 of 2** appeals with an unknown or missing content_id, the response is a 4xx and **nothing** is written to the log.

**Why this target:** The appeal is the only thing between a wrong accusation and no recourse, so it can't be allowed to fail even once. The unknown-id case matters just as much: a typo silently recording an appeal against nothing would make the log lie.

---

## 5. Bad input never crashes the service

Of 7 malformed submissions (missing `text`, empty text, whitespace-only text, `text` that is a number, a body that is a JSON list, missing `creator_id`, and 100,000 characters of text), **0 return a 500 or hang**. Every one returns a JSON error with a 4xx status, and every one leaves a rejection entry in the log.

**Why this target:** A crash on malformed input is one of the most common real failures, and it is also the cheapest attack to try. I want every refusal to be a clean answer with a reason, and I want it logged so an attack can't be invisible.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 8 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath, like this:

         ## 2. Uncertain cases land in the unsure band

         The system handles uncertain cases well.

         **Why this target:** ...

         > **Revised in unit 8:** Text I judged borderline scores between
         > 0.4 and 0.6 in at least 4 of 5 cases.
         >
         > **Why revised:** "well" gave me nothing to check. I couldn't
         > reach a verdict from it at all.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "At most 1 of 10 of my own pieces flagged as AI" → "at most 3
            of 10", because 1 of 10 turned out to be hard.

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->

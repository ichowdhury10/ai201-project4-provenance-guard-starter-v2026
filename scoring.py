"""
Turning two numbers into one, and one number into something a person can read.
← YOU BUILD THIS IN MILESTONES 4 AND 5

Two functions live here, and both are stubs.

`combine_signals` is where your false-positive decision from Milestone 1
actually gets made. Everything above it — the labels, the appeal path — is
downstream of a number this function produced.

`score_to_label` is where you stop writing for a machine and start writing for
a person. A score of 0.62 means nothing to a writer.

⚠️ Your README's **Signals and Scoring** section has to name the file and
function holding your combining rule. The grader checks your code against what
you claim, so that line should read `scoring.py::combine_signals`.
"""

import config


def combine_signals(model_score: float, style_score: float) -> float:
    """
    Combine two 0-1 signals into one 0-1 score. Higher = more likely AI.

    The rule (numbers live in config.py):

      1. Weighted average: 0.5 * model_score + 0.5 * style_score.
      2. Disagreement: if the two signals are more than 0.25 apart, pull the
         average halfway back toward 0.5. Two methods disagreeing IS
         uncertainty, so the result lands nearer the middle and the writer gets
         the "unsure" label rather than an accusation resting on one signal.

    Why equal weights: on my calibration set (calibrate.py) the model signal
    separates clear AI from clear human better, but it also scores plain human
    writing as machine-like, and the style signal is the only thing that
    differs on those pieces. Neither deserves to win outright.

    Why the AI line, not the weights, carries the false-positive decision: see
    AI_THRESHOLD in config.py.
    """
    avg = (
        config.WEIGHT_MODEL_SIGNAL * model_score
        + config.WEIGHT_STYLE_SIGNAL * style_score
    )
    if abs(model_score - style_score) > config.DISAGREEMENT_GAP:
        avg = 0.5 + (avg - 0.5) * (1 - config.DISAGREEMENT_SHRINK)
    return round(min(max(avg, 0.0), 1.0), 4)


def confidence(score: float) -> float:
    """
    How sure the system is of its guess, 0-1: 0 at a score of 0.5 (a coin
    flip), 1 at 0.0 or 1.0. This is distance from the middle, doubled.
    """
    return round(abs(score - 0.5) * 2, 4)


LABEL_AI = (
    "Our checks found patterns in this text that are common in AI-written "
    "text, but they can't prove it, and plain, simple writing by people can "
    "look this way too. If you wrote this yourself, please tell us. You can "
    "appeal, and a person will look at it."
)
LABEL_HUMAN = "We think this was probably written by a person."
LABEL_UNSURE = (
    "We can't tell how this was written. Our checks didn't point clearly "
    "either way, so we're not drawing a conclusion. Nothing is held against "
    "you, and you don't need to do anything."
)


def score_to_label(score: float) -> tuple[str, str]:
    """
    Turn a score into (guess, label_text). Every score from 0 to 1 maps to
    exactly one of three: <= HUMAN_THRESHOLD human, >= AI_THRESHOLD ai,
    otherwise unsure.
    """
    if score >= config.AI_THRESHOLD:
        return "ai", LABEL_AI
    if score <= config.HUMAN_THRESHOLD:
        return "human", LABEL_HUMAN
    return "unsure", LABEL_UNSURE


def label_ranges() -> list[tuple[str, str]]:
    """
    The score range each label covers. Your README needs these beside the
    label text — given to you so the numbers can't drift apart from config.py.
    """
    return [
        ("high-confidence human", f"0.00 – {config.HUMAN_THRESHOLD:.2f}"),
        ("unsure", f"{config.HUMAN_THRESHOLD:.2f} – {config.AI_THRESHOLD:.2f}"),
        ("high-confidence AI", f"{config.AI_THRESHOLD:.2f} – 1.00"),
    ]

"""
Signal two: the style signal. ← YOU BUILD THIS IN MILESTONE 4

Signal one reads the text for meaning. This one measures it *as text* — the
shape of it, without understanding a word.

Three measures are stubbed below because the brief names those three. They are
stubs, not implementations: what they compute is yours, and so is how you
combine them.

    sentence_length_spread   do sentences vary in length, or march in step?
    type_token_ratio         how much of the vocabulary repeats?
    punctuation_density      how much punctuation, and how varied?

Why these might differ between human and AI writing: generated prose tends
toward even, mid-length sentences and a narrower band of vocabulary, because
that's what "most likely next word" produces on average. Human writing is
lumpier — a three-word sentence next to a forty-word one.

⚠️ **The blind spot, which you have to name in Milestone 1.**

This signal cannot read. It has no idea what the text says. Anything that
changes the shape without changing the substance moves it — adding typos,
breaking up sentences, pasting in a quotation. That is a very cheap thing for
someone to do on purpose, and unit 8's attack set will do it to you.

Build each function on its own and call it from a terminal before you wire
anything together:

    python stylometry.py "some text to look at"
"""

import re
import statistics


def sentences(text: str) -> list[str]:
    """Split into sentences. Rough and good enough — given to you."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def words(text: str) -> list[str]:
    """Split into lowercase words, punctuation stripped. Given to you."""
    return re.findall(r"[a-z0-9']+", text.lower())


# ── The three measures ───────────────────────────────────────────────────────
#
# Directions (written down because the combining rule depends on them):
#   sentence_length_spread  raw: coefficient of variation (stdev / mean) of
#                           sentence length in words. HIGH = lumpy = more human.
#   type_token_ratio        raw: unique words / total words (windowed, see below).
#                           HIGH = varied vocabulary = more human.
#   punctuation_density     raw: how much non-terminal punctuation there is and
#                           how many different marks are used. HIGH = more human.
# style_signal() flips each of them so that 1.0 means "more likely AI".

MIN_WORDS = 20        # below this the measures are too noisy to lean on
TTR_WINDOW = 50       # TTR is computed over windows this size (length-fair)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def sentence_length_spread(text: str) -> float:
    """
    Coefficient of variation of sentence length, in words (stdev / mean).

    Raw scale: roughly 0 (every sentence the same length) to 1+ (very lumpy).
    Higher = more human. A single sentence has no spread to measure, so it
    returns 0.5 (the "can't tell" middle of the useful range) rather than
    raising.
    """
    lengths = [len(words(s)) for s in sentences(text)]
    lengths = [n for n in lengths if n > 0]
    if len(lengths) < 2:
        return 0.5
    mean = statistics.mean(lengths)
    if mean == 0:
        return 0.5
    return statistics.stdev(lengths) / mean


def mean_sentence_length(text: str) -> float:
    """Average sentence length in words (0.0 for empty text)."""
    lengths = [len(words(x)) for x in sentences(text)]
    lengths = [n for n in lengths if n > 0]
    return statistics.mean(lengths) if lengths else 0.0


def type_token_ratio(text: str) -> float:
    """
    Unique words over total words, 0–1. Higher = more varied vocabulary.

    Plain TTR falls as text gets longer, so for 50+ words this averages the
    ratio over sliding windows of 50 words (a moving-average TTR). That keeps a
    long text and a short one roughly comparable.
    """
    ws = words(text)
    if not ws:
        return 0.0
    if len(ws) <= TTR_WINDOW:
        return len(set(ws)) / len(ws)
    step = max(1, TTR_WINDOW // 2)
    ratios = [
        len(set(ws[i:i + TTR_WINDOW])) / TTR_WINDOW
        for i in range(0, len(ws) - TTR_WINDOW + 1, step)
    ]
    return sum(ratios) / len(ratios)


# Marks inside a sentence. Full stops are left out on purpose: they track
# sentence count, which the spread measure already covers.
_MARKS = [",", ";", ":", "—", "–", "-", "(", '"', "'", "!", "?", "…"]


def punctuation_density(text: str) -> float:
    """
    How much non-terminal punctuation there is, blended with how many different
    marks are used. Roughly 0 (none) to 1 (lots and varied). Higher = more human.

    Half is density (marks per word, saturating at 0.15), half is variety (how
    many of the 12 tracked marks appear, saturating at 5).
    """
    ws = words(text)
    if not ws:
        return 0.0
    counts = [text.count(m) for m in _MARKS]
    density = sum(counts) / len(ws)
    variety = sum(1 for c in counts if c > 0)
    return 0.5 * _clamp(density / 0.15) + 0.5 * _clamp(variety / 5)


# ── Combining them ───────────────────────────────────────────────────────────

# Each measure is rescaled to 0–1 "AI-ness" with a linear ramp between a value
# that looks clearly AI (1.0) and one that looks clearly human (0.0).
STYLE_WEIGHTS = {"spread": 0.35, "ttr": 0.15, "punct": 0.30, "length": 0.20}


def _ramp(value: float, ai_at: float, human_at: float) -> float:
    return _clamp((value - human_at) / (ai_at - human_at))


def style_parts(text: str) -> dict:
    """The three rescaled parts (0–1, higher = more AI-like), for debugging."""
    return {
        "spread": round(_ramp(sentence_length_spread(text), ai_at=0.25, human_at=0.75), 3),
        "ttr": round(_ramp(type_token_ratio(text), ai_at=0.55, human_at=0.85), 3),
        "punct": round(_ramp(punctuation_density(text), ai_at=0.25, human_at=0.75), 3),
        # Typical chatbot prose averages 14+ words a sentence. Very short
        # average sentences (under ~8 words) are not what a chatbot defaults to,
        # so they push toward human. Added after calibration showed plain,
        # short-sentence human writing scoring as AI on every other measure.
        "length": round(_ramp(mean_sentence_length(text), ai_at=14, human_at=8), 3),
    }


def style_signal(text: str) -> float:
    """
    The style signal as a 0–1 score. **Higher means more likely AI.**

    Weighted sum of four rescaled parts (spread 0.35, vocabulary 0.15,
    punctuation 0.30, mean sentence length 0.20). Texts under MIN_WORDS words are pulled toward 0.5,
    because three numbers from a dozen words are mostly noise.
    """
    parts = style_parts(text)
    score = sum(STYLE_WEIGHTS[k] * parts[k] for k in STYLE_WEIGHTS)

    n = len(words(text))
    if n < MIN_WORDS:
        trust = n / MIN_WORDS
        score = 0.5 + (score - 0.5) * trust

    return round(_clamp(score), 4)


if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or (
        "The system works well. It handles most cases correctly and provides "
        "good results. Users generally find it easy to use and understand."
    )

    print(f"{len(sentences(text))} sentences, {len(words(text))} words\n")
    print(f"sentence_length_spread   {sentence_length_spread(text)}")
    print(f"type_token_ratio         {type_token_ratio(text)}")
    print(f"punctuation_density      {punctuation_density(text)}")
    print(f"parts (0-1, AI-ward)     {style_parts(text)}")
    print(f"style_signal             {style_signal(text)}   (higher = more likely AI)")

"""
Calibration set for Milestone 4. Run:  python calibrate.py

Prints both signals side by side for pieces I chose on purpose, so the combining
rule and the thresholds are set against evidence rather than a guess.

The groups:
  ai          clearly machine-style prose (written to imitate typical chatbot output)
  human       clearly human: voice, tangents, specifics, uneven sentences
  plain       plain, conventional human writing (the false-positive risk)
  formal      formal human writing
  edited_ai   AI-style text with light human editing
"""

import detector
import scoring
import stylometry

SAMPLES = {
    "ai": [
        "Climate change is one of the most pressing challenges facing our world today. It affects ecosystems, economies, and communities across the globe. To address it effectively, it is important to consider a variety of solutions. Renewable energy, sustainable agriculture, and international cooperation all play a crucial role. By working together, we can build a more sustainable future for generations to come.",
        "Effective time management is an essential skill for success in both personal and professional life. It allows individuals to prioritize tasks, reduce stress, and achieve their goals efficiently. There are several key strategies that can help improve time management. These include setting clear goals, creating a schedule, and minimizing distractions. Ultimately, consistent practice leads to lasting improvement.",
        "Artificial intelligence is transforming the way we live and work. It offers numerous benefits, including increased efficiency, improved decision-making, and enhanced customer experiences. However, it also presents important challenges that must be carefully considered. Issues such as privacy, bias, and job displacement require thoughtful solutions. Overall, the responsible development of AI is essential for a positive future.",
        "The ocean is a vital part of our planet's ecosystem. It provides food, regulates the climate, and supports a vast diversity of life. Unfortunately, pollution and overfishing threaten its health. It is important for individuals and governments to take action to protect marine environments. With collective effort, we can ensure that the ocean remains healthy and productive for the future.",
        "Reading is a valuable habit that offers many benefits. It improves vocabulary, enhances focus, and expands knowledge of the world. Furthermore, it can reduce stress and promote relaxation. To build a reading habit, it is helpful to set aside a regular time each day. Choosing books that match your interests can also make the experience more enjoyable and rewarding.",
    ],
    "human": [
        "My grandmother kept a jar of buttons on the windowsill, and nobody was ever allowed to touch it. Not that we wanted to. It rattled when the trains went by, which was every twenty minutes, and she'd say, without looking up, 'That's the 4:10.' It was never the 4:10. I think about that jar more than I think about her, which is a terrible thing to admit.",
        "Okay so the bus broke down outside Harlow, right, and the driver just sat there eating a sandwich like nothing had happened. Forty of us. Forty! A woman near the back started singing hymns — badly — and somehow that made it better. I got home at 2am smelling like diesel and wet wool, and honestly? Best commute of my life.",
        "I don't trust recipes that say 'season to taste.' Taste what? Whose taste? When I was twelve I put a whole tablespoon of cayenne in a chili because the card said 'a pinch' and my hands were bigger than the card's author's, apparently. My dad ate two bowls and cried a little. We never spoke of it again, but he asks for it every winter.",
        "The lab smelled of burnt coffee and something chemical I never could name. Dr. Pruitt would pace — three steps, turn, three steps — muttering about funding while we pretended not to listen. Then, out of nowhere, a grin. 'It's the buffer,' he said. It was the buffer. It's always the buffer, and yet we spent a month everywhere else.",
        "Honestly I only started running because my landlord's dog hated me. Two blocks, that was my limit; by the third I was wheezing like a kettle. Now it's six miles before work, and the dog (Biscuit, a menace) actually wags when I pass. Funny how that goes. Nobody tells you that the thing you do out of spite can quietly turn into the thing you love.",
    ],
    "plain": [
        "I went to the store on Saturday. I bought milk, eggs, and bread. The store was very busy. I waited in line for a long time. Then I went home and made breakfast. My sister came over and we ate together. It was a good day. I like weekends because I can rest.",
        "My favorite season is summer. I like summer because it is warm. I can go to the beach with my friends. We swim and play games. We eat ice cream. The days are long so there is more time to play. I am sad when summer ends. School starts again and I have to wake up early.",
        "Last year my family moved to a new city. It was hard at first. I did not know anyone. My school was big and I got lost a lot. But then I met a boy named Tom. He showed me around. Now we are best friends. I am happy we moved here. It is a good place to live.",
    ],
    "formal": [
        "The committee convened on the fourteenth to consider the petition. Having reviewed the submissions, it found that the applicant's reliance upon the earlier precedent, while understandable, was misplaced; the circumstances there were materially distinguishable. Accordingly, the motion was denied, without prejudice to renewal upon a fuller evidentiary record.",
        "Notwithstanding the manifest shortcomings of the early quantum models, Bohr's 1913 synthesis retains considerable pedagogical value: it renders the discrete spectral lines of hydrogen intelligible by a single, audacious postulate — that angular momentum is quantised — and thereby anticipates, albeit crudely, the wave-mechanical treatment that would supplant it.",
    ],
    "edited_ai": [
        "Climate change is, honestly, the biggest thing facing us right now. It hits ecosystems, economies, towns — everyone. To deal with it we need lots of different fixes. Solar and wind help, so does better farming, and countries have to actually cooperate (which, ugh). If we work together we can leave something decent for our kids.",
        "Time management is a skill that matters at work and at home. It helps you rank tasks, cut stress and hit your goals. A few things help: set clear goals, make a schedule, kill distractions. Keep at it and you'll see a real change. Not overnight, mind you, but eventually.",
    ],
}


def run():
    rows = []
    for group, texts in SAMPLES.items():
        for i, t in enumerate(texts, 1):
            m = detector.model_signal(t)
            s = stylometry.style_signal(t)
            c = scoring.combine_signals(m, s)
            guess, _ = scoring.score_to_label(c)
            rows.append((f"{group}-{i}", m, s, c, guess))
    print(f"{'piece':<12}{'model':>8}{'style':>8}{'combined':>10}  guess")
    print("-" * 46)
    for name, m, s, c, g in rows:
        print(f"{name:<12}{m:>8.3f}{s:>8.3f}{c:>10.3f}  {g}")
    print()
    for group in SAMPLES:
        sel = [r for r in rows if r[0].startswith(group + "-")]
        avg = lambda k: sum(r[k] for r in sel) / len(sel)
        print(f"{group:<10} mean model {avg(1):.3f}  style {avg(2):.3f}  combined {avg(3):.3f}")


if __name__ == "__main__":
    run()

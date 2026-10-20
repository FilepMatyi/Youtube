from __future__ import annotations

import re

from .models import ClipCandidate, TranscriptSegment

ENERGY_WORDS = {
    "amazing", "awesome", "best", "crazy", "secret", "shocking", "unbelievable", "important",
    "never", "always", "why", "how", "wow", "laugh", "funny", "incredible", "actually",
    "elképesztő", "hihetetlen", "titok", "legjobb", "fontos", "soha", "mindig", "miért",
    "hogyan", "durva", "őrület", "vicces", "valójában", "figyelj",
}

HOOK_WORDS = {
    "here's", "imagine", "secret", "truth", "mistake", "reason", "actually", "listen",
    "watch", "this", "most", "never", "what", "why", "how", "nobody", "everyone",
}
FILLER_WORDS = {"um", "uh", "erm", "like", "basically", "literally", "okay", "so"}


def _window_score(items: list[TranscriptSegment], start: float, end: float) -> tuple[float, str]:
    selected = [s for s in items if s.end > start and s.start < end]
    text = " ".join(s.text for s in selected).strip()
    tokens = re.findall(r"[\wáéíóöőúüű'-]+", text.lower())
    duration = max(1.0, end - start)
    speech_density = len(tokens) / duration
    keyword_hits = sum(token in ENERGY_WORDS for token in tokens)
    questions = text.count("?")
    exclamations = text.count("!")
    first_words = tokens[:18]
    hook_score = min(7.0, sum(word in HOOK_WORDS for word in first_words) * 1.7)
    filler_ratio = sum(word in FILLER_WORDS for word in tokens) / max(1, len(tokens))
    unique_ratio = len(set(tokens)) / max(1, len(tokens))
    # Reward conversational density, immediate hooks/emotion, variety, and a clean ending.
    density_score = 8.0 * min(speech_density / 2.8, 1.0)
    energy_score = min(keyword_hits * 1.8 + questions * 1.2 + exclamations * 1.1, 12.0)
    length_score = 4.0 if 40 <= duration <= 50 else 0.0
    ending_score = 2.0 if text.rstrip().endswith((".", "!", "?")) else -1.0
    silence_penalty = sum(max(0.0, b.start - a.end - 1.5) for a, b in zip(selected, selected[1:]))
    filler_penalty = filler_ratio * 20
    repetition_penalty = max(0.0, 0.42 - unique_ratio) * 16
    return (
        density_score + energy_score + hook_score + length_score + ending_score
        - silence_penalty * 1.5 - filler_penalty - repetition_penalty,
        text,
    )


def select_clips(
    segments: list[TranscriptSegment], video_duration: float, count: int = 5, clip_length: int = 45
) -> list[ClipCandidate]:
    clip_length = max(40, min(50, clip_length))
    if video_duration <= clip_length:
        score, text = _window_score(segments, 0, video_duration)
        return [ClipCandidate(0, video_duration, score, "Best moment", text)]

    candidates: list[ClipCandidate] = []
    # Start on actual speech boundaries and finish near the end of a sentence.
    # Trying 40/45/50s lets the scorer choose coherence rather than an arbitrary timestamp.
    possible_starts = sorted({max(0.0, round(s.start, 2)) for s in segments})
    for raw_start in possible_starts:
        for candidate_length in sorted({40, clip_length, 45, 50}):
            if raw_start + 40 > video_duration:
                continue
            target_end = min(raw_start + candidate_length, video_duration)
            ending_segments = [s for s in segments if target_end - 4 <= s.end <= target_end + 4]
            end = min(ending_segments, key=lambda s: abs(s.end - target_end)).end if ending_segments else target_end
            end = min(end, video_duration)
            if not 40 <= end - raw_start <= 50:
                continue
            start = raw_start
            score, text = _window_score(segments, start, end)
            if text:
                words = re.findall(r"\w+", text)
                title = " ".join(words[:7]) + ("…" if len(words) > 7 else "")
                candidates.append(ClipCandidate(start, end, score, title or "Highlight", text))

    chosen: list[ClipCandidate] = []
    for candidate in sorted(candidates, key=lambda c: c.score, reverse=True):
        overlap = any(max(0.0, min(candidate.end, x.end) - max(candidate.start, x.start)) > 5 for x in chosen)
        if not overlap:
            chosen.append(candidate)
        if len(chosen) == count:
            break
    return sorted(chosen, key=lambda c: c.start)

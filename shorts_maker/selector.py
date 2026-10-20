from __future__ import annotations

import re
from bisect import bisect_left, bisect_right

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


def _window_score(
    items: list[TranscriptSegment], start: float, end: float, minimum: float = 40, maximum: float = 50
) -> tuple[float, str, dict[str, float]]:
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
    length_score = 4.0 if minimum <= duration <= maximum else 0.0
    ending_score = 2.0 if text.rstrip().endswith((".", "!", "?")) else -1.0
    silence_penalty = sum(max(0.0, b.start - a.end - 1.5) for a, b in zip(selected, selected[1:]))
    filler_penalty = filler_ratio * 20
    repetition_penalty = max(0.0, 0.42 - unique_ratio) * 16
    first_token = tokens[0] if tokens else ""
    context_penalty = 2.0 if first_token in {"and", "but", "because", "he", "she", "they", "it", "és", "de", "mert", "ő"} else 0.0
    storytelling_score = min(3.0, max(0, sum(text.count(mark) for mark in ".!?")) * 0.75)
    breakdown = {
        "speech_density": round(density_score, 2),
        "hook": round(hook_score, 2),
        "interestingness_proxy": round(energy_score, 2),
        "story_structure_proxy": round(storytelling_score, 2),
        "length": round(length_score, 2),
        "ending": round(ending_score, 2),
        "silence_penalty": round(-silence_penalty * 1.5, 2),
        "filler_penalty": round(-filler_penalty, 2),
        "repetition_penalty": round(-repetition_penalty, 2),
        "context_penalty": round(-context_penalty, 2),
    }
    return sum(breakdown.values()), text, breakdown


def _similarity(first: str, second: str) -> float:
    def shingles(text: str) -> set[tuple[str, str, str]]:
        words = re.findall(r"\w+", text.lower())
        return set(zip(words, words[1:], words[2:]))

    left, right = shingles(first), shingles(second)
    return len(left & right) / max(1, len(left | right))


def select_clips(
    segments: list[TranscriptSegment], video_duration: float, count: int = 5, clip_length: int = 45,
    length_range: tuple[int, int] = (40, 50),
) -> list[ClipCandidate]:
    minimum, maximum = length_range
    if not 15 <= minimum <= maximum <= 180:
        raise ValueError("Clip range must be between 15 and 180 seconds.")
    clip_length = max(minimum, min(maximum, clip_length))
    if video_duration <= minimum:
        score, text, breakdown = _window_score(segments, 0, video_duration, minimum, maximum)
        return [ClipCandidate(0, video_duration, score, "Best moment", text, breakdown, "Rövid forrásvideó.")] if text else []

    candidates: list[ClipCandidate] = []
    # Start on actual speech boundaries and finish near the end of a sentence.
    # Trying 40/45/50s lets the scorer choose coherence rather than an arbitrary timestamp.
    # One natural start per small bucket keeps long-video analysis fast.
    starts_by_bucket = {}
    bucket_width = max(2, min(8, minimum // 8))
    for segment in segments:
        starts_by_bucket.setdefault(int(segment.start // bucket_width), max(0.0, round(segment.start, 2)))
    possible_starts = sorted(starts_by_bucket.values())
    ordered_segments = sorted(segments, key=lambda item: item.start)
    segment_starts = [item.start for item in ordered_segments]
    segment_ends = [item.end for item in ordered_segments]
    for raw_start in possible_starts:
        for candidate_length in sorted({minimum, clip_length, (minimum + maximum) // 2, maximum}):
            if raw_start + minimum > video_duration:
                continue
            target_end = min(raw_start + candidate_length, video_duration)
            ending_margin = max(3, min(8, candidate_length // 10))
            end_low = bisect_left(segment_ends, target_end - ending_margin)
            end_high = bisect_right(segment_ends, target_end + ending_margin)
            ending_segments = ordered_segments[end_low:end_high]
            end = min(ending_segments, key=lambda s: abs(s.end - target_end)).end if ending_segments else target_end
            end = min(end, video_duration)
            if not minimum <= end - raw_start <= maximum:
                continue
            start = raw_start
            first_index = bisect_right(segment_ends, start)
            last_index = bisect_left(segment_starts, end)
            score, text, breakdown = _window_score(
                ordered_segments[first_index:last_index], start, end, minimum, maximum
            )
            if text:
                words = re.findall(r"\w+", text)
                if len(words) < max(8, int((end - start) * 0.45)):
                    continue
                title = " ".join(words[:7]) + ("…" if len(words) > 7 else "")
                reasons = []
                if breakdown["hook"] > 0:
                    reasons.append("figyelemfelkeltő nyitás")
                if breakdown["speech_density"] >= 4:
                    reasons.append("folyamatos beszéd")
                if breakdown["ending"] > 0:
                    reasons.append("lezárt gondolat")
                if breakdown["silence_penalty"] < -2:
                    reasons.append("hosszabb szünet")
                explanation = ", ".join(reasons) or "beszédalapú jelölt"
                candidates.append(ClipCandidate(start, end, score, title or "Highlight", text, breakdown, explanation))

    # Weighted interval scheduling finds the best *set* of clips. Greedy ranking
    # can choose one excellent middle clip that blocks two other strong clips.
    candidates.sort(key=lambda c: (c.end, c.start))
    ends = [candidate.end for candidate in candidates]
    overlap_tolerance = min(5.0, minimum * 0.1)
    previous = [bisect_right(ends, candidate.start + overlap_tolerance, 0, index) for index, candidate in enumerate(candidates)]
    n = len(candidates)
    if n == 0:
        return []
    scores = [[0.0] * (n + 1)] + [[float("-inf")] * (n + 1) for _ in range(count)]
    selected = [[False] * (n + 1) for _ in range(count + 1)]
    for amount in range(1, count + 1):
        for index, candidate in enumerate(candidates, 1):
            skip = scores[amount][index - 1]
            take = scores[amount - 1][previous[index - 1]] + candidate.score
            if take > skip:
                scores[amount][index] = take
                selected[amount][index] = True
            else:
                scores[amount][index] = skip

    amount = next((value for value in range(count, 0, -1) if scores[value][n] != float("-inf")), 0)
    chosen: list[ClipCandidate] = []
    index = n
    while amount and index:
        if selected[amount][index]:
            chosen.append(candidates[index - 1])
            index = previous[index - 1]
            amount -= 1
        else:
            index -= 1
    unique: list[ClipCandidate] = []
    for candidate in sorted(chosen, key=lambda c: (-c.score, c.start)):
        if not any(_similarity(candidate.transcript, other.transcript) > 0.82 for other in unique):
            unique.append(candidate)
    for candidate in sorted(candidates, key=lambda c: (-c.score, c.start)):
        if len(unique) >= count:
            break
        if any(
            max(0.0, min(candidate.end, other.end) - max(candidate.start, other.start)) > overlap_tolerance
            or _similarity(candidate.transcript, other.transcript) > 0.82
            for other in unique
        ):
            continue
        unique.append(candidate)
    return unique

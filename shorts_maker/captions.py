from __future__ import annotations

from pathlib import Path

from .models import TranscriptSegment, Word


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int(seconds % 3600 // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _groups(words: list[Word], size: int = 4) -> list[list[Word]]:
    """Create readable social-video caption chunks, breaking early at punctuation."""
    result: list[list[Word]] = []
    current: list[Word] = []
    for word in words:
        current.append(word)
        if len(current) >= size or word.text.rstrip().endswith((".", "!", "?", ",")):
            result.append(current)
            current = []
    if current:
        result.append(current)
    return result


def create_ass(segments: list[TranscriptSegment], clip_start: float, clip_end: float, output: Path) -> None:
    words = [w for s in segments for w in s.words if w.end > clip_start and w.start < clip_end]
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Shorts,Arial,82,&H00FFFFFF,&H0000FFFF,&H00101010,&H80000000,-1,0,0,0,100,100,1,0,1,6,3,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    if words:
        for group in _groups(words):
            # One event per spoken word: the active word becomes yellow, briefly
            # scales up, then settles. The surrounding words remain visible.
            for active_index, active in enumerate(group):
                start = max(0.0, active.start - clip_start)
                end = min(clip_end - clip_start, active.end - clip_start + 0.04)
                if end <= start:
                    continue
                rendered: list[str] = []
                for index, word in enumerate(group):
                    value = _escape(word.text.upper())
                    if index == active_index:
                        rendered.append(
                            rf"{{\c&H00D7FF&\fscx122\fscy122\t(0,140,\fscx100\fscy100)}}{value}{{\rShorts}}"
                        )
                    else:
                        rendered.append(value)
                caption = " ".join(rendered)
                lines.append(
                    f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Shorts,,0,0,0,,"
                    rf"{{\fad(45,45)}}{caption}" + "\n"
                )
    else:
        # Older Whisper results can omit word timing; keep usable phrase captions.
        for segment in segments:
            if segment.end <= clip_start or segment.start >= clip_end:
                continue
            start = max(0.0, segment.start - clip_start)
            end = min(clip_end - clip_start, segment.end - clip_start)
            lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Shorts,,0,0,0,,{_escape(segment.text.upper())}\n")
    output.write_text("".join(lines), encoding="utf-8-sig")

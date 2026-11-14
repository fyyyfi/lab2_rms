"""Підтримувані формати та допоміжні функції."""
from pathlib import Path

AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

FILE_FILTER = (
    "Медіафайли (" + " ".join(f"*{e}" for e in sorted(AUDIO_EXT | VIDEO_EXT)) + ");;"
    "Аудіо (" + " ".join(f"*{e}" for e in sorted(AUDIO_EXT)) + ");;"
    "Відео (" + " ".join(f"*{e}" for e in sorted(VIDEO_EXT)) + ");;"
    "Усі файли (*)"
)


def is_media(path: str) -> bool:
    return Path(path).suffix.lower() in AUDIO_EXT | VIDEO_EXT


def kind(source: str) -> str:
    """'audio' | 'video' | 'stream' — для підказки в інтерфейсі."""
    if source.startswith(("http://", "https://", "rtsp://")):
        return "stream"
    return "audio" if Path(source).suffix.lower() in AUDIO_EXT else "video"


def fmt_ms(ms: int) -> str:
    """Мілісекунди -> 'h:mm:ss' або 'm:ss'."""
    if ms is None or ms < 0:
        ms = 0
    s = ms // 1000
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

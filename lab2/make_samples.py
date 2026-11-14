"""Генерує тестові медіафайли у media/ за допомогою FFmpeg:
два аудіо (WAV, MP3, FLAC) і два відео (MP4/H.264, WebM/VP9) по ~20 с."""
import subprocess
from pathlib import Path

OUT = Path(__file__).parent / "media"
OUT.mkdir(exist_ok=True)

JOBS = {
    "tone_chord.wav": ["-f", "lavfi", "-i", "sine=frequency=220:duration=20",
                       "-f", "lavfi", "-i", "sine=frequency=277:duration=20",
                       "-f", "lavfi", "-i", "sine=frequency=330:duration=20",
                       "-filter_complex", "amix=inputs=3,afade=t=in:d=1,afade=t=out:st=18:d=2"],
    "melody.mp3": ["-f", "lavfi", "-i",
                   "aevalsrc='0.4*sin(2*PI*(440+110*floor(mod(t*2,4)))*t)':s=44100:d=20",
                   "-c:a", "libmp3lame", "-b:a", "160k",
                   "-metadata", "title=Тестова мелодія", "-metadata", "artist=make_samples.py"],
    "noise_sweep.flac": ["-f", "lavfi", "-i", "anoisesrc=d=20:c=pink:a=0.2",
                         "-af", "lowpass=f=1500,afade=t=in:d=3"],
    "testcard.mp4": ["-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=20",
                     "-f", "lavfi", "-i", "sine=frequency=523:duration=20",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"],
    "mandelbrot.webm": ["-f", "lavfi", "-i", "mandelbrot=size=854x480:rate=25",
                        "-f", "lavfi", "-i", "sine=frequency=330:duration=20",
                        "-t", "20", "-c:v", "libvpx-vp9", "-b:v", "1M", "-c:a", "libopus"],
}

for name, args in JOBS.items():
    dst = OUT / name
    if not dst.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args, str(dst)], check=True)
    print(f"{name:20s} {dst.stat().st_size / 1024:8.0f} КБ")

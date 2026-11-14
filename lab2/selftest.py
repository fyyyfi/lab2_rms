"""Автоматична перевірка програвача: відкриває кожен файл із media/ (і URL,
якщо передано), перевіряє тривалість, наявність відео, перемотування,
паузу і стоп. Звук під час тесту вимкнено.

Запуск:  python selftest.py [URL]
"""
import sys
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

from player.formats import fmt_ms
from player.window import PlayerWindow


def wait(ms, until=None, win=None):
    loop = QEventLoop()
    t = QTimer(); t.setInterval(50)
    left = [ms]

    def tick():
        left[0] -= 50
        if left[0] <= 0 or (until and until()):
            loop.quit()
    t.timeout.connect(tick); t.start(); loop.exec(); t.stop()


def check(win: PlayerWindow, url: QUrl) -> dict:
    p = win.player
    win.load_and_play(url)
    wait(15000, lambda: p.mediaStatus() in (QMediaPlayer.BufferedMedia, QMediaPlayer.InvalidMedia)
         and p.duration() > 0)
    res = {"src": url.fileName() or url.toString(), "dur": fmt_ms(p.duration()),
           "video": p.hasVideo(), "ok": p.error() == QMediaPlayer.NoError and p.duration() > 0}
    wait(1200)
    res["playing"] = p.playbackState() == QMediaPlayer.PlayingState and p.position() > 0
    step = min(10_000, p.duration() // 3)        # для коротких кліпів крок менший
    before = p.position()
    win.seek_by(step); wait(600)
    res["seek+10"] = p.position() >= before + step - 1_000
    before = p.position()
    win.seek_by(-step); wait(600)
    res["seek-10"] = p.position() <= before - step + 1_000
    win.slider.sliderMoved.emit(p.duration() // 2); wait(600)
    res["slider"] = abs(p.position() - p.duration() // 2) < 2_500
    win.toggle_play(); wait(300)
    res["pause"] = p.playbackState() == QMediaPlayer.PausedState
    win.stop(); wait(300)
    res["stop"] = p.playbackState() == QMediaPlayer.StoppedState and p.position() == 0
    return res


def main():
    app = QApplication(sys.argv[:1])
    win = PlayerWindow(); win.audio.setMuted(True); win.show()
    urls = [QUrl.fromLocalFile(str(f.resolve())) for f in sorted(Path("media").iterdir())
            if not f.name.startswith(".")]
    urls += [QUrl(u) for u in sys.argv[1:]]
    fails = 0
    for u in urls:
        r = check(win, u)
        flags = [k for k in ("ok", "playing", "seek+10", "seek-10", "slider", "pause", "stop") if not r[k]]
        fails += bool(flags)
        print(f"{r['src'][:60]:60s} {r['dur']:>6s} {'відео' if r['video'] else 'аудіо':6s} "
              f"{'OK' if not flags else 'FAIL: ' + ', '.join(flags)}")
    win.close()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

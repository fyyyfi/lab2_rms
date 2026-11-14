"""Головне вікно програвача."""
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl, Slot
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
    QMessageBox, QSlider, QSplitter, QStackedWidget, QStyle, QToolButton,
    QVBoxLayout, QWidget,
)

from .formats import FILE_FILTER, fmt_ms, is_media, kind
from .playlist import Playlist

SEEK_STEP_MS = 10_000          # крок перемотування кнопками ⏪ / ⏩
SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]


class SeekSlider(QSlider):
    """Повзунок прогресу: клік у довільне місце одразу переносить позицію."""

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.maximum() > 0:
            value = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), int(event.position().x()), self.width())
            self.setValue(value)
            self.sliderMoved.emit(value)
        super().mousePressEvent(event)


class PlayerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Медіаплеєр")
        self.resize(1100, 640)
        self.setAcceptDrops(True)
        self.settings = QSettings("ipz-labs", "mediaplayer")

        # --- ядро відтворення -------------------------------------------
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.video = QVideoWidget()
        self.player.setVideoOutput(self.video)

        # заглушка для аудіофайлів (відео нема — показуємо назву і метадані)
        self.audio_card = QLabel("Відкрийте файл (Ctrl+O) або URL (Ctrl+U)\n"
                                 "чи перетягніть файли у вікно")
        self.audio_card.setAlignment(Qt.AlignCenter)
        self.audio_card.setStyleSheet("background:#1e1f24;color:#d7d9e0;font-size:18px;")
        self.screen = QStackedWidget()
        self.screen.addWidget(self.audio_card)   # 0
        self.screen.addWidget(self.video)        # 1

        self.playlist = Playlist()
        self.playlist.activated_url.connect(self.load_and_play)

        self._build_controls()
        self._build_menu()

        split = QSplitter()
        split.addWidget(self.screen)
        split.addWidget(self.playlist)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 1)
        split.setSizes([820, 260])

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.addWidget(split, 1)
        lay.addLayout(self.controls)
        self.setCentralWidget(central)
        self.status = self.statusBar()

        # --- сигнали плеєра --------------------------------------------
        self.player.durationChanged.connect(self.on_duration)
        self.player.positionChanged.connect(self.on_position)
        self.player.playbackStateChanged.connect(self.on_state)
        self.player.mediaStatusChanged.connect(self.on_media_status)
        self.player.errorOccurred.connect(self.on_error)
        self.player.metaDataChanged.connect(self.on_metadata)
        self.player.hasVideoChanged.connect(
            lambda has: self.screen.setCurrentIndex(1 if has else 0))

        self.set_volume(int(self.settings.value("volume", 70)))

    # ================================================================ UI ===
    def _btn(self, icon: QStyle.StandardPixmap, tip: str, slot) -> QToolButton:
        b = QToolButton()
        b.setIcon(self.style().standardIcon(icon))
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.clicked.connect(slot)
        return b

    def _build_controls(self):
        S = QStyle.StandardPixmap
        self.btn_prev = self._btn(S.SP_MediaSkipBackward, "Попередній у плейлисті", self.playlist.previous)
        self.btn_back = self._btn(S.SP_MediaSeekBackward, "Назад на 10 с (←)", lambda: self.seek_by(-SEEK_STEP_MS))
        self.btn_play = self._btn(S.SP_MediaPlay, "Відтворення / пауза (Пробіл)", self.toggle_play)
        self.btn_stop = self._btn(S.SP_MediaStop, "Стоп", self.stop)
        self.btn_fwd = self._btn(S.SP_MediaSeekForward, "Вперед на 10 с (→)", lambda: self.seek_by(SEEK_STEP_MS))
        self.btn_next = self._btn(S.SP_MediaSkipForward, "Наступний у плейлисті", self.playlist.next)

        self.slider = SeekSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.player.setPosition)
        self.lbl_time = QLabel("0:00 / 0:00")
        self.lbl_time.setMinimumWidth(110)
        self.lbl_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.btn_mute = self._btn(S.SP_MediaVolume, "Вимкнути звук (M)", self.toggle_mute)
        self.vol = QSlider(Qt.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setFixedWidth(110)
        self.vol.valueChanged.connect(self.set_volume)
        self.lbl_vol = QLabel()
        self.lbl_vol.setMinimumWidth(36)

        self.speed = QComboBox()
        for s in SPEEDS:
            self.speed.addItem(f"{s:g}×", s)
        self.speed.setCurrentIndex(SPEEDS.index(1.0))
        self.speed.setToolTip("Швидкість відтворення")
        self.speed.currentIndexChanged.connect(
            lambda i: self.player.setPlaybackRate(self.speed.itemData(i)))

        row = QHBoxLayout()
        for w in (self.btn_prev, self.btn_back, self.btn_play, self.btn_stop,
                  self.btn_fwd, self.btn_next):
            row.addWidget(w)
        row.addWidget(self.slider, 1)
        row.addWidget(self.lbl_time)
        row.addSpacing(12)
        row.addWidget(self.btn_mute)
        row.addWidget(self.vol)
        row.addWidget(self.lbl_vol)
        row.addWidget(self.speed)
        self.controls = row

    def _build_menu(self):
        m_file = self.menuBar().addMenu("&Файл")
        self._action(m_file, "Відкрити файл…", QKeySequence.Open, self.open_files)
        self._action(m_file, "Відкрити URL…", "Ctrl+U", self.open_url)
        m_file.addSeparator()
        self._action(m_file, "Вийти", QKeySequence.Quit, self.close)

        m_play = self.menuBar().addMenu("&Відтворення")
        self._action(m_play, "Відтворення / пауза", Qt.Key_Space, self.toggle_play)
        self._action(m_play, "Стоп", "S", self.stop)
        self._action(m_play, "Назад 10 с", Qt.Key_Left, lambda: self.seek_by(-SEEK_STEP_MS))
        self._action(m_play, "Вперед 10 с", Qt.Key_Right, lambda: self.seek_by(SEEK_STEP_MS))
        self._action(m_play, "Гучніше", Qt.Key_Up, lambda: self.vol.setValue(self.vol.value() + 5))
        self._action(m_play, "Тихіше", Qt.Key_Down, lambda: self.vol.setValue(self.vol.value() - 5))
        self._action(m_play, "Без звуку", "M", self.toggle_mute)
        self._action(m_play, "На весь екран", "F", self.toggle_fullscreen)

        m_list = self.menuBar().addMenu("&Плейлист")
        self._action(m_list, "Наступний", "N", self.playlist.next)
        self._action(m_list, "Попередній", "P", self.playlist.previous)
        self._action(m_list, "Видалити вибраний", QKeySequence.Delete, self.playlist.remove_current)
        self._action(m_list, "Очистити", None, self.playlist.clear)

    def _action(self, menu, text, shortcut, slot):
        a = QAction(text, self)
        if shortcut is not None:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        menu.addAction(a)
        self.addAction(a)          # гарячі клавіші працюють і в повноекранному режимі
        return a

    # =========================================================== джерела ===
    @Slot()
    def open_files(self):
        start = self.settings.value("last_dir", str(Path.home()))
        paths, _ = QFileDialog.getOpenFileNames(self, "Відкрити медіафайл", start, FILE_FILTER)
        if paths:
            self.settings.setValue("last_dir", str(Path(paths[0]).parent))
            self.add_paths(paths, play_first=True)

    @Slot()
    def open_url(self):
        last = self.settings.value("last_url", "https://")
        text, ok = QInputDialog.getText(self, "Відкрити URL",
                                        "Адреса аудіо/відео (http, https, HLS .m3u8):", text=last)
        url = QUrl(text.strip()) if ok else QUrl()
        if not ok or not text.strip():
            return
        if not url.isValid() or url.scheme() not in ("http", "https", "rtsp"):
            QMessageBox.warning(self, "Невірна адреса", f"Не вдається розпізнати URL:\n{text}")
            return
        self.settings.setValue("last_url", url.toString())
        self.playlist.play_row(self.playlist.add(url))

    def add_paths(self, paths, play_first=False):
        rows = [self.playlist.add_path(p) for p in paths if Path(p).is_file()]
        if rows and play_first:
            self.playlist.play_row(rows[0])

    @Slot(QUrl)
    def load_and_play(self, url: QUrl):
        self.player.stop()
        self.player.setSource(url)
        name = url.fileName() if url.isLocalFile() else url.toString()
        self.audio_card.setText(f"♪\n{name}")
        self.screen.setCurrentIndex(0)
        self.setWindowTitle(f"{name} — Медіаплеєр")
        self.status.showMessage(f"Завантаження: {name}")
        self.player.play()

    # ========================================================== керування ===
    @Slot()
    def toggle_play(self):
        if self.player.source().isEmpty():
            self.open_files()
        elif self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    @Slot()
    def stop(self):
        self.player.stop()          # позиція повертається на початок

    def seek_by(self, delta_ms: int):
        if self.player.isSeekable():
            pos = max(0, min(self.player.duration(), self.player.position() + delta_ms))
            self.player.setPosition(pos)

    @Slot(int)
    def set_volume(self, value: int):
        value = max(0, min(100, value))
        if self.vol.value() != value:
            self.vol.setValue(value)
        # лінійний повзунок -> логарифмічна (перцептивна) гучність
        from PySide6.QtMultimedia import QtAudio
        self.audio.setVolume(QtAudio.convertVolume(
            value / 100, QtAudio.VolumeScale.LogarithmicVolumeScale,
            QtAudio.VolumeScale.LinearVolumeScale))
        self.lbl_vol.setText(f"{value}%")
        self.settings.setValue("volume", value)

    @Slot()
    def toggle_mute(self):
        self.audio.setMuted(not self.audio.isMuted())
        S = QStyle.StandardPixmap
        self.btn_mute.setIcon(self.style().standardIcon(
            S.SP_MediaVolumeMuted if self.audio.isMuted() else S.SP_MediaVolume))

    @Slot()
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.playlist.show()
        else:
            self.playlist.hide()
            self.showFullScreen()

    # ========================================================= сигнали ===
    @Slot(int)
    def on_duration(self, ms: int):
        self.slider.setRange(0, ms)
        self._update_time()

    @Slot(int)
    def on_position(self, ms: int):
        if not self.slider.isSliderDown():
            self.slider.setValue(ms)
        self._update_time()

    def _update_time(self):
        dur = self.player.duration()
        total = fmt_ms(dur) if dur > 0 else "—"      # для live-потоку тривалість невідома
        self.lbl_time.setText(f"{fmt_ms(self.player.position())} / {total}")

    @Slot(QMediaPlayer.PlaybackState)
    def on_state(self, state):
        S = QStyle.StandardPixmap
        playing = state == QMediaPlayer.PlayingState
        self.btn_play.setIcon(self.style().standardIcon(S.SP_MediaPause if playing else S.SP_MediaPlay))

    @Slot(QMediaPlayer.MediaStatus)
    def on_media_status(self, status):
        names = {
            QMediaPlayer.LoadingMedia: "Завантаження…",
            QMediaPlayer.BufferingMedia: "Буферизація…",
            QMediaPlayer.StalledMedia: "Очікування даних…",
            QMediaPlayer.LoadedMedia: "Готово",
            QMediaPlayer.BufferedMedia: "Відтворення",
            QMediaPlayer.InvalidMedia: "Формат не підтримується",
        }
        if status == QMediaPlayer.LoadedMedia:
            self.on_metadata()
        if status in names:
            self.status.showMessage(f"{names[status]}  [{kind(self.player.source().toString())}]")
        if status == QMediaPlayer.EndOfMedia and not self.playlist.next():
            self.player.setPosition(0)
            self.status.showMessage("Кінець плейлиста")

    @Slot()
    def on_metadata(self):
        md = self.player.metaData()
        parts = [md.stringValue(k) for k in (QMediaMetaData.Title, QMediaMetaData.ContributingArtist,
                                             QMediaMetaData.AlbumTitle)]
        parts = [p for p in parts if p]
        res = md.value(QMediaMetaData.Resolution)
        if res is not None and not res.isEmpty():
            parts.append(f"{res.width()}×{res.height()}")
        codec = md.stringValue(QMediaMetaData.AudioCodec)
        if codec:
            parts.append(codec)
        if parts and not self.player.hasVideo():
            name = self.player.source().fileName() or self.player.source().toString()
            self.audio_card.setText(f"♪\n{name}\n\n" + " · ".join(parts))

    @Slot(QMediaPlayer.Error, str)
    def on_error(self, error, message):
        if error != QMediaPlayer.NoError:
            QMessageBox.critical(self, "Помилка відтворення",
                                 f"{self.player.source().toString()}\n\n{message}")

    # ===================================================== drag & drop ===
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        locals_ = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        remote = [u for u in e.mimeData().urls() if not u.isLocalFile()]
        self.add_paths([p for p in locals_ if is_media(p)], play_first=True)
        for u in remote:
            self.playlist.add(u)

    def mouseDoubleClickEvent(self, e):
        if self.screen.geometry().contains(e.position().toPoint()):
            self.toggle_fullscreen()

    def closeEvent(self, e):
        self.player.stop()
        super().closeEvent(e)

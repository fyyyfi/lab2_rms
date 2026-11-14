"""Плейлист: список джерел (локальні файли та URL) з поточною позицією."""
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem


class Playlist(QListWidget):
    """Список відтворення. Кожен елемент зберігає QUrl у Qt.UserRole."""

    activated_url = Signal(QUrl)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.itemDoubleClicked.connect(lambda it: self._activate(self.row(it)))

    # --- наповнення -------------------------------------------------------
    def add(self, url: QUrl) -> int:
        title = url.fileName() if url.isLocalFile() else url.toString()
        item = QListWidgetItem(("🌐 " if not url.isLocalFile() else "") + title)
        item.setData(Qt.UserRole, url)
        item.setToolTip(url.toString())
        self.addItem(item)
        return self.count() - 1

    def add_path(self, path: str) -> int:
        return self.add(QUrl.fromLocalFile(str(Path(path).resolve())))

    def remove_current(self) -> None:
        row = self.currentRow()
        if row >= 0:
            self.takeItem(row)

    # --- навігація --------------------------------------------------------
    def url_at(self, row: int) -> QUrl | None:
        item = self.item(row)
        return item.data(Qt.UserRole) if item else None

    def _activate(self, row: int) -> None:
        url = self.url_at(row)
        if url is not None:
            self.setCurrentRow(row)
            self.activated_url.emit(url)

    def play_row(self, row: int) -> bool:
        if 0 <= row < self.count():
            self._activate(row)
            return True
        return False

    def next(self) -> bool:
        return self.play_row(self.currentRow() + 1)

    def previous(self) -> bool:
        return self.play_row(self.currentRow() - 1)

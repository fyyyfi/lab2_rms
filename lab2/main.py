"""Запуск:  python main.py [файл_або_URL ...]"""
import sys

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from player.window import PlayerWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Медіаплеєр")
    win = PlayerWindow()
    win.show()
    args = sys.argv[1:]
    if args:
        for a in args:
            if "://" in a:
                win.playlist.add(QUrl(a))
            else:
                win.playlist.add_path(a)
        win.playlist.play_row(0)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

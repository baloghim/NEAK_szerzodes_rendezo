import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5 import QtCore, QtWidgets
from app.gui import Window


def test_default_startup_and_settings(tmp_path, monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(QtCore.QStandardPaths, 'writableLocation', lambda kind: str(tmp_path))
    window = Window()
    window.folder.setText(str(tmp_path))
    window.store.set_setting('folder', str(tmp_path))
    window.tabs.setCurrentIndex(1)
    window.close()
    reopened = Window()
    assert reopened.folder.text() == str(tmp_path)
    assert reopened.tabs.currentIndex() == 1
    reopened.close()

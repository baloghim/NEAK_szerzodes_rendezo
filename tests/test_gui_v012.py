import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import threading
import time
import pytest
from PyQt5 import QtCore, QtWidgets as W
from app.gui import Window, Preview, SettingsDialog, PathLabel
from app.core import Store, Contract
from app.documents import Recognition
from test_rotation import make_pdf, rotations


@pytest.fixture
def app():
    app=W.QApplication.instance() or W.QApplication([])
    yield app


@pytest.fixture
def window(tmp_path,app):
    settings=tmp_path/'settings';settings.mkdir()
    db=Store(settings/'contracts.sqlite3');db.set_setting('folder',str(tmp_path));db.db.close()
    window=Window(settings)
    window.error=lambda message: (_ for _ in ()).throw(AssertionError(str(message)))
    yield window
    deadline=time.monotonic()+5
    while any(job.isRunning() for job in window.jobs) and time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
    window.close()


def test_settings_persist_and_main_path_is_informational(window,tmp_path,app):
    dialog=SettingsDialog(window.store)
    destination=tmp_path/'archive';destination.mkdir()
    dialog.folder.setText(str(destination))
    dialog.auto_ocr.setChecked(False);dialog.auto_preview.setChecked(False)
    dialog.view.setCurrentText('100%')
    dialog.apply(window.store)
    window.apply_settings()
    assert isinstance(window.folder,PathLabel)
    assert window.folder.toolTip()==str(destination)
    assert not any(button.text()=='Mappa kiválasztása…' for button in window.findChildren(W.QPushButton))
    reopened=Store(Path(window.store.db.execute('PRAGMA database_list').fetchone()[2]))
    settings=SettingsDialog(reopened)
    assert settings.folder.text()==str(destination)
    assert not settings.auto_ocr.isChecked() and not settings.auto_preview.isChecked()
    assert settings.view.currentText()=='100%'
    reopened.db.close()


def test_manual_preview_rotation_is_per_page_and_source_unchanged(window,tmp_path):
    source=tmp_path/'source.pdf';make_pdf(source)
    original=source.read_bytes()
    preview=window.scan_preview
    state=window.rotation_state(str(source))
    preview.open(source,state)
    preview.rotate(90)
    assert preview.rotation_map()=={0:90}
    preview.turn(1);preview.rotate(-90)
    assert preview.rotation_map()=={0:90,1:270}
    preview.open(source,state)
    assert preview.rotation_map()=={0:90,1:270}
    assert source.read_bytes()==original
    assert rotations(source)==[0,0]


def test_archive_rotation_requires_confirmation(window,tmp_path,monkeypatch):
    source=tmp_path/'source.pdf';make_pdf(source)
    original=source.read_bytes()
    preview=window.browse_preview
    preview.open(source,window.rotation_state(str(source)))
    preview.rotate(90)
    confirmations=[]
    def no(*args):confirmations.append(args);return W.QMessageBox.No
    monkeypatch.setattr(W.QMessageBox,'question',no)
    window.save_rotation(preview)
    assert confirmations and source.read_bytes()==original
    monkeypatch.setattr(W.QMessageBox,'question',lambda *args:W.QMessageBox.Yes)
    window.store.mark(source,'Feltöltve')
    timestamp=window.store.status(source)[1]
    window.save_rotation(preview)
    assert rotations(source)==[90,0]
    assert window.store.status(source)==('Feltöltve',timestamp)
    assert not any(preview.rotation_map().values())


def test_pending_scan_saves_rotated_copy_only(window,tmp_path,monkeypatch):
    source=tmp_path/'source.pdf';make_pdf(source)
    original=source.read_bytes()
    monkeypatch.setattr(window,'start_next',lambda:None)
    window.add_files([str(source)])
    data=Contract('T123','Szintetikus Kft.','Szintetikus','IX-3','20260201')
    window.load_fields(data)
    window.scan_preview.rotate(90)
    window.save_rotation(window.scan_preview)
    assert source.read_bytes()==original
    window.confirm.setChecked(True);window.next_check.setChecked(False)
    window.save()
    assert rotations(tmp_path/data.filename())==[90,0]
    assert source.read_bytes()==original


@pytest.mark.parametrize('fail',[False,True])
def test_real_processing_lifecycle_and_animation(window,tmp_path,app,monkeypatch,fail):
    import app.gui as gui
    source=tmp_path/'input.pdf';make_pdf(source,1)
    started=threading.Event();release=threading.Event()
    def recognize(*args,**kwargs):
        started.set()
        assert release.wait(5)
        if fail:raise OSError('synthetic OCR failure')
        return Recognition('NEAK-kód: T123\nSzolgáltató neve: Szintetikus\nIX/3.\nHatályos: 2026.02.01.')
    monkeypatch.setattr(gui,'recognize',recognize)
    window.store.provider('T123','Szintetikus','Szintetikus')
    try:
        window.add_files([str(source)])
        assert started.wait(2)
        entry=window.items[str(source)]
        assert entry['state']=='Feldolgozás'
        assert entry['item'].data(QtCore.Qt.UserRole+1)=='Feldolgozás'
        assert window.pulse.isActive() and window.pulse.interval()>=100
    finally:release.set()
    deadline=time.monotonic()+5
    while time.monotonic()<deadline and (entry['state']=='Feldolgozás' or any(j.isRunning() for j in window.jobs)):
        app.processEvents();time.sleep(.01)
    assert entry['state']==('Feldolgozási hiba' if fail else 'Felismerve')
    assert not window.pulse.isActive()


def test_full_tab_and_panel_titles(window,app):
    window.resize(1024,768);window.show();app.processEvents()
    assert window.tabs.elideMode()==QtCore.Qt.ElideNone
    for index in range(window.tabs.count()):
        rect=window.tabs.tabBar().tabRect(index)
        assert rect.width()>=window.tabs.tabBar().fontMetrics().horizontalAdvance(window.tabs.tabText(index))+20
    for panel in window.findChildren(W.QGroupBox):
        assert panel.minimumWidth()>=panel.fontMetrics().horizontalAdvance(panel.title())+20

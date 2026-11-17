import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import threading
import time
import pytest
from PyQt5 import QtCore, QtWidgets as W
from app.core import Store, Contract, available_years
from app.documents import Recognition
from app.gui import Window, DateItem
from test_rotation import make_pdf


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
    deadline=time.monotonic()+10
    while any(job.isRunning() for job in window.jobs) and time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
    window.close()


def populate(window,tmp_path,app):
    names=['T123_Minta_IX-1_20240101.pdf','T123_Minta_IX-2_20250201.pdf',
           'T123_Minta_IX-3_20260101.pdf','T124_Masik_IX-3_20261231.pdf',
           'T125_Archived_IX-1_20230101.pdf','T126_Future_IX-1_20270101.pdf',
           'T127_Bad_IX-1_20260230.pdf','unrecognized.pdf']
    for name in names:make_pdf(tmp_path/name,1)
    window.store.mark(tmp_path/names[2],'Feltöltve')
    window.refresh()
    window.resize(1280,850);window.show();app.processEvents()
    return [tmp_path/name for name in names]


def visible(window):
    return {window.table.item(row,0).text() for row in range(window.table.rowCount())
            if not window.table.isRowHidden(row)}


def row_for(window,path):
    return next(row for row in range(window.table.rowCount())
                if window.table.item(row,0).data(QtCore.Qt.UserRole)==str(path))


@pytest.mark.parametrize('year,expected',[(2026,['2026','2025','2024']),
                                        (2027,['2027','2026','2025','2024']),
                                        (2024,['2024'])])
def test_calendar_years(year,expected):assert available_years(year)==expected


def test_year_filters_combine_and_reset_without_writes(window,tmp_path,app):
    paths=populate(window,tmp_path,app)
    before={p:p.read_bytes() for p in paths}
    statuses=list(window.store.db.execute('SELECT * FROM documents ORDER BY path'))
    window.refresh_years(2026)
    assert window.year_filter.currentText()=='Összes év' and len(visible(window))==8
    window.year_filter.setCurrentText('2026')
    assert visible(window)=={paths[2].name,paths[3].name}
    window.search.setText('T123');window.annex_filter.setCurrentText('IX-3')
    window.status_filter.setCurrentText('Feltöltve')
    assert visible(window)=={paths[2].name}
    window.year_filter.setCurrentText('2025');assert not visible(window)
    window.reset_filter()
    assert window.year_filter.currentText()=='Összes év' and len(visible(window))==8
    window.refresh_years(2027)
    assert [window.year_filter.itemText(i) for i in range(window.year_filter.count())]==['Összes év','2027','2026','2025','2024']
    assert all(p.read_bytes()==before[p] for p in paths)
    assert list(window.store.db.execute('SELECT * FROM documents ORDER BY path'))==statuses


def test_date_column_is_formatted_typed_and_chronological(window,tmp_path,app):
    paths=populate(window,tmp_path,app)
    assert window.table.horizontalHeaderItem(4).text()=='Hatályosság kezdete'
    cell=window.table.item(row_for(window,paths[1]),4)
    assert isinstance(cell,DateItem) and cell.text()=='2025.02.01.'
    assert isinstance(cell.data(QtCore.Qt.UserRole+2),QtCore.QDate)
    for path in paths[-2:]:assert window.table.item(row_for(window,path),4).text()==''
    for order in (QtCore.Qt.AscendingOrder,QtCore.Qt.DescendingOrder):
        window.table.sortItems(4,order)
        dates=[window.table.item(row,4).data(QtCore.Qt.UserRole+2) for row in range(window.table.rowCount())]
        keys=[date.toJulianDay() if date.isValid() else 0 for date in dates]
        assert keys==sorted(keys,reverse=order==QtCore.Qt.DescendingOrder)


def test_context_menu_targets_clicked_row_and_persists(window,tmp_path,app,monkeypatch):
    paths=populate(window,tmp_path,app)
    before={p:p.read_bytes() for p in paths}
    window.table.sortItems(5,QtCore.Qt.AscendingOrder)
    window.table.setCurrentCell(row_for(window,paths[0]),0)
    opened=[]
    def execute(menu,position):
        opened.append([a.text() for a in menu.actions()])
        assert window.selected_path()==str(paths[1])
        menu.actions()[0].trigger()
    monkeypatch.setattr(W.QMenu,'exec_',execute)
    rect=window.table.visualItemRect(window.table.item(row_for(window,paths[1]),0))
    window.table.customContextMenuRequested.emit(rect.center())
    assert opened==[['Megjelölés feltöltöttként','Nincs feltöltve','Ellenőrizendő','Ismeretlen']]
    assert window.store.status(paths[1])[0]=='Feltöltve' and window.store.status(paths[1])[1]
    assert window.store.status(paths[0])==('Ismeretlen',None)
    assert window.table.item(row_for(window,paths[1]),5).text()=='Feltöltve'
    assert window.upload_state.currentText()=='Feltöltve' and 'Feltöltve:' in window.details.text()
    db_path=window.store.db.execute('PRAGMA database_list').fetchone()[2]
    reopened=Store(db_path);assert reopened.status(paths[1])==window.store.status(paths[1]);reopened.db.close()
    window.upload_state.setCurrentText('Ellenőrizendő');window.mark()
    assert window.store.status(paths[1])==('Ellenőrizendő',None)
    assert 'Feltöltve:' not in window.details.text()
    assert all(p.read_bytes()==before[p] for p in paths)


def test_context_empty_area_and_multiselection_are_safe(window,tmp_path,app,monkeypatch):
    paths=populate(window,tmp_path,app)
    opened=[]
    def execute(menu,position):opened.append(1);menu.actions()[1].trigger()
    monkeypatch.setattr(W.QMenu,'exec_',execute)
    window.show_status_menu(QtCore.QPoint(-10,-10));assert not opened
    window.table.setSelectionMode(W.QAbstractItemView.MultiSelection)
    window.table.selectRow(row_for(window,paths[0]));window.table.selectRow(row_for(window,paths[1]))
    rect=window.table.visualItemRect(window.table.item(row_for(window,paths[3]),0))
    window.show_status_menu(rect.center())
    assert len(opened)==1
    assert window.store.status(paths[3])==('Nincs feltöltve',None)
    assert window.store.status(paths[0])==('Ismeretlen',None)
    assert window.store.status(paths[1])==('Ismeretlen',None)
    assert len(window.table.selectionModel().selectedRows())==1


def test_clear_resets_all_scan_details_but_preserves_archive_and_settings(window,tmp_path,app,monkeypatch):
    paths=populate(window,tmp_path,app)
    window.store.provider('T123','Szintetikus Kft.','Szintetikus')
    config=list(window.store.db.execute('SELECT * FROM settings ORDER BY key'))
    providers=list(window.store.db.execute('SELECT * FROM providers'))
    records=list(window.store.db.execute('SELECT * FROM documents ORDER BY path'))
    original={p:p.read_bytes() for p in paths}
    monkeypatch.setattr(window,'start_next',lambda:None)
    window.add_files([str(paths[0])])
    window.load_fields(Contract('T123','Szintetikus Kft.','Szintetikus','IX-3','20260201',['synthetic warning']))
    window.set_queue_state(str(paths[0]),'Felismerve')
    window.confirm.setChecked(True)
    window.scan_preview.turn(0);window.scan_preview.rotate(90);window.scan_preview.zoom(1.25)
    assert window.save_button.isEnabled()
    window.clear_queue()
    assert not window.items and not window.pending and window.queue.count()==0 and window.current is None
    assert all((edit.currentText() if isinstance(edit,W.QComboBox) else edit.text())=='' for edit in window.fields.values())
    assert window.filename.text()=='' and window.warning.text()=='' and not window.confirm.isChecked()
    assert window.scan_preview.document is None and window.scan_preview.path is None
    assert window.scan_preview.index==0 and window.scan_preview.scale==1.0 and window.scan_preview.counter.text()=='0 / 0'
    assert window.scan_preview.label.pixmap() is None
    assert not window.save_button.isEnabled() and not window.pulse.isActive()
    assert window.folder.text()==str(tmp_path)
    assert list(window.store.db.execute('SELECT * FROM settings ORDER BY key'))==config
    assert list(window.store.db.execute('SELECT * FROM providers'))==providers
    assert list(window.store.db.execute('SELECT * FROM documents ORDER BY path'))==records
    assert all(p.read_bytes()==original[p] for p in paths)


def test_late_worker_result_after_clear_and_same_path_reimport_is_ignored(window,tmp_path,app,monkeypatch):
    import app.gui as gui
    source=tmp_path/'source.pdf';make_pdf(source,1)
    started=threading.Event();release=threading.Event()
    def slow(*args,**kwargs):
        started.set();assert release.wait(5)
        return Recognition('NEAK-kód: T123\nSzolgáltató neve: OLD RESULT\nIX/3.\nHatályos: 2026.02.01.',{0:90})
    monkeypatch.setattr(gui,'recognize',slow)
    window.add_files([str(source)])
    try:
        assert started.wait(2)
        old_token=window.jobs[0].token
        window.clear_queue()
        # Re-add the same pathname before the old worker returns. This used to
        # let an old result attach to a completely new queue entry.
        original_start=window.start_next
        monkeypatch.setattr(window,'start_next',lambda:None)
        window.add_files([str(source)])
        assert old_token!=(window.session_id,window.items[str(source)]['token'])
        window.recognized(str(source),Contract('T123','STALE','STALE','IX-3','20260201'),'',
                          {'token':old_token,'rotations':{0:90}})
        assert window.fields['provider'].text()=='' and window.rotation_state(str(source))['auto']=={}
        window.pending.clear()  # This test intentionally does not start another OCR.
    finally:release.set()
    deadline=time.monotonic()+5
    while any(j.isRunning() for j in window.jobs) and time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
    app.processEvents()
    assert window.fields['provider'].text()=='' and window.items[str(source)]['state']=='Várakozik'
    assert not window.save_button.isEnabled()
    window.clear_queue()
    assert window.warning.text()=='' and window.scan_preview.counter.text()=='0 / 0'

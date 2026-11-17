"""Synthetic v0.1.3 functional check, also run inside the packaged EXE."""
from pathlib import Path
from PyQt5 import QtCore, QtWidgets as W
from .core import Contract, Store


def run(window, root, source):
    root=Path(root)
    paths=[root/'T123_Szintetikus_IX-1_20240101.pdf',root/'T124_Szintetikus_IX-2_20241231.pdf']
    for path in paths:path.write_bytes(Path(source).read_bytes())
    originals={path:path.read_bytes() for path in paths}
    window.refresh()
    window.year_filter.setCurrentText('2024')
    visible={window.table.item(row,0).data(QtCore.Qt.UserRole) for row in range(window.table.rowCount())
             if not window.table.isRowHidden(row)}
    assert visible==set(map(str,paths)),visible
    window.table.sortItems(4,QtCore.Qt.DescendingOrder)
    row=next(row for row in range(window.table.rowCount())
             if window.table.item(row,0).data(QtCore.Qt.UserRole)==str(paths[0]))
    assert window.table.item(row,4).text()=='2024.01.01.'
    assert isinstance(window.table.item(row,4).data(QtCore.Qt.UserRole+2),QtCore.QDate)
    original_exec=W.QMenu.exec_
    try:
        # Exercise the production QAction connection without requiring mouse input
        # on a CI runner's desktop. The context location is an actual table cell.
        W.QMenu.exec_=lambda menu,pos:menu.actions()[0].trigger()
        position=window.table.visualItemRect(window.table.item(row,0)).center()
        window.show_status_menu(position)
    finally:W.QMenu.exec_=original_exec
    assert window.store.status(paths[0])[0]=='Feltöltve'
    assert window.store.status(paths[0])[1]
    assert window.store.status(paths[1])==('Ismeretlen',None)
    assert window.upload_state.currentText()=='Feltöltve'
    window.upload_state.setCurrentText('Ellenőrizendő');window.mark()
    assert window.store.status(paths[0])==('Ellenőrizendő',None)
    assert 'Feltöltve:' not in window.details.text()
    db_path=window.store.db.execute('PRAGMA database_list').fetchone()[2]
    reopened=Store(db_path)
    assert reopened.status(paths[0])==('Ellenőrizendő',None)
    reopened.db.close()
    records=list(window.store.db.execute('SELECT * FROM documents ORDER BY path'))
    settings=list(window.store.db.execute('SELECT * FROM settings ORDER BY key'))
    providers=list(window.store.db.execute('SELECT * FROM providers ORDER BY code'))
    window.load_fields(Contract('T123','Szintetikus','Szintetikus','IX-1','20240101',['synthetic warning']))
    window.confirm.setChecked(True)
    folder=window.folder.text()
    window.clear_queue()
    assert window.queue.count()==0 and not window.items and not window.pending
    assert not window.save_button.isEnabled() and not window.confirm.isChecked()
    assert all((field.currentText() if isinstance(field,W.QComboBox) else field.text())=='' for field in window.fields.values())
    assert window.filename.text()=='' and window.warning.text()==''
    assert window.scan_preview.document is None and window.scan_preview.index==0
    assert window.scan_preview.counter.text()=='0 / 0' and not window.scan_preview.rotation_save_action.isEnabled()
    assert window.folder.text()==folder
    assert list(window.store.db.execute('SELECT * FROM documents ORDER BY path'))==records
    assert list(window.store.db.execute('SELECT * FROM settings ORDER BY key'))==settings
    assert list(window.store.db.execute('SELECT * FROM providers ORDER BY code'))==providers
    assert all(path.read_bytes()==originals[path] for path in paths)
    window.reset_filter()
    print('PASS: packaged year/date filters, single-row context status persistence and complete session reset')

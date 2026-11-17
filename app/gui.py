import base64
import json
import os
from pathlib import Path
import sys
import tempfile
from PyQt5 import QtCore, QtGui, QtWidgets as W
import pypdfium2 as pdfium
from .core import Contract, Store, STATUSES, extract_contract, parse_filename, save_copy, digest
from .documents import recognize, import_files


class Worker(QtCore.QThread):
    result = QtCore.pyqtSignal(object, object, str)

    def __init__(self, path, providers):
        super().__init__()
        self.path, self.providers = path, providers

    def run(self):
        try:
            self.result.emit(self.path, extract_contract(recognize(self.path), self.providers), '')
        except Exception as error:
            self.result.emit(self.path, Contract(warnings=[str(error)]), str(error))


class Preview(W.QWidget):
    def __init__(self):
        super().__init__()
        self.document = None
        self.index = 0
        self.scale = 1.0
        self.fit = True
        layout = W.QVBoxLayout(self)
        bar = W.QHBoxLayout()
        for label, action in [('◀', lambda: self.turn(-1)), ('▶', lambda: self.turn(1)),
                              ('−', lambda: self.zoom(.8)), ('+', lambda: self.zoom(1.25)),
                              ('Oldalszélesség', self.fit_width)]:
            button = W.QPushButton(label)
            button.clicked.connect(action)
            bar.addWidget(button)
        self.counter = W.QLabel('0 / 0')
        bar.addWidget(self.counter)
        layout.addLayout(bar)
        self.scroll = W.QScrollArea()
        self.label = W.QLabel('Válassz dokumentumot')
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.scroll.setWidget(self.label)
        layout.addWidget(self.scroll)

    def open(self, path):
        if self.document:
            self.document.close()
        self.document = None
        self.index = 0
        try:
            self.document = pdfium.PdfDocument(str(path))
            self.render()
        except Exception as error:
            self.label.setText('A PDF nem jeleníthető meg: ' + str(error))
            self.label.adjustSize()

    def turn(self, amount):
        if self.document:
            self.index = max(0, min(len(self.document) - 1, self.index + amount))
            self.render()

    def zoom(self, factor):
        self.fit = False
        self.scale = max(.2, min(5, self.scale * factor))
        self.render()

    def fit_width(self):
        self.fit = True
        self.render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit:
            self.render()

    def render(self):
        if not self.document:
            return
        try:
            page = self.document[self.index]
            scale = max(.2, (self.scroll.viewport().width() - 24) / page.get_width()) if self.fit else self.scale
            self.scale = scale
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil().convert('RGB')
            data = image.tobytes()
            qimage = QtGui.QImage(data, image.width, image.height, image.width * 3, QtGui.QImage.Format_RGB888).copy()
            self.label.setPixmap(QtGui.QPixmap.fromImage(qimage))
            self.label.resize(image.width, image.height)
            self.counter.setText(f'{self.index + 1} / {len(self.document)}')
            page.close()
        except Exception as error:
            self.label.setText(str(error))


class Window(W.QMainWindow):
    def __init__(self, data_dir=None):
        super().__init__()
        root = Path(data_dir) if data_dir else Path(W.QStandardPaths.writableLocation(W.QStandardPaths.AppLocalDataLocation))
        root.mkdir(parents=True, exist_ok=True)
        self.store = Store(root / 'contracts.sqlite3')
        self.staging = tempfile.TemporaryDirectory(prefix='neak-import-')
        self.jobs = []
        self.items = {}
        self.pending = []
        self.current = None
        self.loading = False
        self.setWindowTitle('Otthonápolási szerződéskezelő – v0.1.0')
        self.resize(1500, 900)
        self.setAcceptDrops(True)
        self.setStyleSheet('QGroupBox {font-weight:bold; margin-top:18px; border:1px solid #b4c8dd; border-radius:4px;} QGroupBox::title {subcontrol-origin:margin; background:#d5e5f6; padding:5px;} QPushButton {padding:6px;} QLineEdit,QComboBox {padding:4px;} QTabBar::tab:selected {font-weight:bold; background:#e6f0fb;}')
        self.tabs = W.QTabWidget()
        self.setCentralWidget(self.tabs)
        self.scan_page()
        self.browse_page()
        self.tabs.currentChanged.connect(self.view_changed)
        menu = self.menuBar().addMenu('Beállítások')
        menu.addAction('Szerződésmappa…', self.choose_folder)
        menu.addAction('Szolgáltatói törzsadatok…', self.edit_providers)
        self.statusBar().showMessage('Kész – minden feldolgozás helyben történik')
        self.folder.setText(self.store.setting('folder'))
        self.tabs.setCurrentIndex(int(self.store.setting('view', '0')))
        for key, splitter in [('scan', self.scan_split), ('browse', self.browse_split)]:
            state = self.store.setting(key)
            if state:
                splitter.restoreState(QtCore.QByteArray.fromBase64(state.encode()))
        geometry = self.store.setting('geometry')
        if geometry:
            self.restoreGeometry(QtCore.QByteArray.fromBase64(geometry.encode()))
        self.refresh()
        if not self.folder.text():
            QtCore.QTimer.singleShot(200, self.choose_folder)

    def button(self, text, action, layout):
        button = W.QPushButton(text)
        button.clicked.connect(action)
        layout.addWidget(button)
        return button

    def panel(self, title):
        box = W.QGroupBox(title)
        layout = W.QVBoxLayout(box)
        return box, layout

    def scan_page(self):
        self.scan_split = W.QSplitter()
        self.tabs.addTab(self.scan_split, 'Szkennelések feldolgozása')
        box, layout = self.panel('Beérkezett dokumentumok')
        layout.addWidget(W.QLabel('Húzz ide PDF-, MSG- vagy EML-fájlokat\nEgyszerre több dokumentum is hozzáadható.'))
        self.queue = W.QListWidget()
        self.queue.currentItemChanged.connect(self.select_queue)
        layout.addWidget(self.queue)
        bar = W.QHBoxLayout()
        self.button('Hozzáadás…', self.add_dialog, bar)
        self.button('Törlés', self.remove_current, bar)
        self.button('Lista ürítése', self.clear_queue, bar)
        layout.addLayout(bar)
        self.scan_split.addWidget(box)
        box, layout = self.panel('Felismert adatok')
        form = W.QFormLayout()
        self.fields = {}
        for key, title in [('code', 'NEAK-kód'), ('provider', 'Szolgáltató'), ('short', 'Rövid név'), ('annex', 'Melléklet'), ('date', 'Hatályosság kezdete')]:
            edit = W.QComboBox() if key == 'annex' else W.QLineEdit()
            if key == 'annex':
                edit.addItems(['', 'IX-1', 'IX-2', 'IX-3'])
                edit.currentTextChanged.connect(self.update_filename)
            else:
                edit.textChanged.connect(self.update_filename)
            self.fields[key] = edit
            form.addRow(title, edit)
        self.filename = W.QLineEdit()
        form.addRow('Javasolt fájlnév', self.filename)
        self.folder = W.QLineEdit()
        form.addRow('Mentési mappa', self.folder)
        self.button('Mappa kiválasztása…', self.choose_folder, layout)
        layout.addLayout(form)
        self.warning = W.QLabel()
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)
        self.confirm = W.QCheckBox('A felismert adatokat ellenőriztem')
        layout.addWidget(self.confirm)
        self.next_check = W.QCheckBox('Mentés után következő dokumentum')
        self.next_check.setChecked(True)
        layout.addWidget(self.next_check)
        layout.addStretch()
        bar = W.QHBoxLayout()
        self.button('Felismerés újra', self.rerun, bar)
        self.button('Kihagyás', self.next_item, bar)
        self.button('Mentés és következő', self.save, bar)
        layout.addLayout(bar)
        self.scan_split.addWidget(box)
        self.scan_preview = Preview()
        self.scan_split.addWidget(self.scan_preview)
        self.scan_split.setSizes([350, 450, 650])

    def browse_page(self):
        self.browse_split = W.QSplitter()
        self.tabs.addTab(self.browse_split, 'Szerződések tallózása')
        box, layout = self.panel('Szűrők és csoportosítás')
        self.search = W.QLineEdit()
        self.search.setPlaceholderText('NEAK-kód, szolgáltató, fájlnév…')
        self.search.textChanged.connect(self.filter_rows)
        layout.addWidget(self.search)
        self.annex_filter = W.QComboBox()
        self.annex_filter.addItems(['Összes melléklet', 'IX-1', 'IX-2', 'IX-3'])
        self.annex_filter.currentIndexChanged.connect(self.filter_rows)
        layout.addWidget(self.annex_filter)
        self.status_filter = W.QComboBox()
        self.status_filter.addItems(['Összes állapot'] + list(STATUSES))
        self.status_filter.currentIndexChanged.connect(self.filter_rows)
        layout.addWidget(self.status_filter)
        self.button('Frissítés', self.refresh, layout)
        self.button('Szűrés törlése', self.reset_filter, layout)
        layout.addStretch()
        self.browse_split.addWidget(box)
        middle = W.QSplitter(QtCore.Qt.Vertical)
        box, layout = self.panel('Szerződések listája – fejléc kattintásával rendezhető')
        self.table = W.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Fájlnév', 'NEAK-kód', 'Szolgáltató', 'Melléklet', 'Hatályosság', 'ePénz'])
        self.table.setSelectionBehavior(W.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(W.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.select_contract)
        self.table.horizontalHeader().setSectionResizeMode(W.QHeaderView.ResizeToContents)
        layout.addWidget(self.table)
        middle.addWidget(box)
        box, layout = self.panel('Kijelölt szerződés')
        self.details = W.QLabel('Válassz szerződést')
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        self.upload_state = W.QComboBox()
        self.upload_state.addItems(STATUSES)
        layout.addWidget(self.upload_state)
        self.button('Állapot mentése a kijelölt dokumentumhoz', self.mark, layout)
        self.button('PDF megnyitása', self.open_external, layout)
        self.button('Mappa megnyitása', self.open_folder, layout)
        middle.addWidget(box)
        self.browse_split.addWidget(middle)
        self.browse_preview = Preview()
        self.browse_split.addWidget(self.browse_preview)
        self.browse_split.setSizes([220, 650, 650])

    def view_changed(self, index):
        if index == 1:
            self.refresh()

    def error(self, error):
        W.QMessageBox.warning(self, 'Ellenőrizendő', str(error))

    def choose_folder(self):
        folder = W.QFileDialog.getExistingDirectory(self, 'Szerződésmappa kiválasztása', self.folder.text())
        if folder:
            self.folder.setText(folder)
            self.store.set_setting('folder', folder)
            self.refresh()

    def edit_providers(self):
        dialog = W.QDialog(self)
        dialog.setWindowTitle('Szolgáltatói törzsadatok')
        layout = W.QVBoxLayout(dialog)
        layout.addWidget(W.QLabel('Soronként: NEAK-kód;szolgáltató neve;rövid név'))
        editor = W.QPlainTextEdit()
        editor.setPlainText('\n'.join(';'.join(row) for row in self.store.db.execute('SELECT code,name,short FROM providers ORDER BY code')))
        layout.addWidget(editor)
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Save | W.QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec_() == W.QDialog.Accepted:
            try:
                rows = [line.split(';') for line in editor.toPlainText().splitlines() if line.strip()]
                for row in rows:
                    if len(row) != 3:
                        raise ValueError('Minden sor három, pontosvesszővel elválasztott mező legyen.')
                    Contract(row[0].strip().upper(), row[1].strip(), row[2].strip(), 'IX-1', '20260101').validate()
                with self.store.db:
                    self.store.db.execute('DELETE FROM providers')
                    self.store.db.executemany('INSERT INTO providers VALUES (?,?,?)', [(row[0].strip().upper(), row[1].strip(), row[2].strip()) for row in rows])
            except Exception as error:
                self.error(error)

    def add_dialog(self):
        files, _ = W.QFileDialog.getOpenFileNames(self, 'Dokumentumok hozzáadása', '', 'Dokumentumok (*.pdf *.msg *.eml)')
        self.add_files(files)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def add_files(self, files):
        for file in files:
            try:
                paths = import_files([file], self.staging.name)
                for path in paths:
                    if str(path) in self.items:
                        continue
                    item = W.QListWidgetItem(path.name + ' — Várakozik')
                    item.setData(QtCore.Qt.UserRole, str(path))
                    self.queue.addItem(item)
                    self.items[str(path)] = {'item': item, 'data': Contract(), 'state': 'Várakozik'}
                    self.pending.append(str(path))
                if not paths:
                    self.error('Az üzenetben nincs PDF-melléklet.')
            except Exception as error:
                self.error(error)
        self.start_next()
        if self.queue.currentRow() < 0 and self.queue.count():
            self.queue.setCurrentRow(0)

    def start_next(self):
        if any(job.isRunning() for job in self.jobs) or not self.pending:
            return
        path = self.pending.pop(0)
        if path not in self.items:
            self.start_next()
            return
        worker = Worker(path, self.store.providers())
        worker.result.connect(self.recognized)
        worker.finished.connect(self.start_next)
        self.jobs.append(worker)
        worker.start()

    def recognized(self, path, data, error):
        path = str(path)
        if path not in self.items:
            return
        entry = self.items[path]
        entry.update(data=data, state='Ellenőrizendő' if data.warnings else 'Felismerve')
        entry['item'].setText(Path(path).name + ' — ' + entry['state'])
        if self.current == path:
            self.load_fields(data)

    def select_queue(self, item, previous):
        self.stash_fields()
        self.current = item.data(QtCore.Qt.UserRole) if item else None
        if self.current:
            self.load_fields(self.items[self.current]['data'])
            self.scan_preview.open(self.current)

    def contract_fields(self):
        values = {key: edit.currentText() if isinstance(edit, W.QComboBox) else edit.text().strip()
                  for key, edit in self.fields.items()}
        values['code'] = values['code'].upper()
        return Contract(**values)

    def stash_fields(self):
        if self.current in self.items:
            data = self.contract_fields()
            data.warnings = self.items[self.current]['data'].warnings
            self.items[self.current]['data'] = data

    def load_fields(self, data):
        self.loading = True
        for key, edit in self.fields.items():
            if isinstance(edit, W.QComboBox):
                edit.setCurrentText(getattr(data, key))
            else:
                edit.setText(getattr(data, key))
        self.loading = False
        self.warning.setText('\n'.join(data.warnings))
        self.confirm.setChecked(False)
        self.update_filename()

    def update_filename(self):
        if self.loading:
            return
        self.confirm.setChecked(False)
        try:
            self.filename.setText(self.contract_fields().filename())
        except ValueError:
            self.filename.clear()

    def rerun(self):
        if self.current:
            self.pending.append(self.current)
            self.start_next()

    def next_item(self):
        if self.queue.count():
            self.queue.setCurrentRow((self.queue.currentRow() + 1) % self.queue.count())

    def remove_current(self):
        if self.current:
            path = self.current
            item = self.queue.takeItem(self.queue.currentRow())
            self.items.pop(path, None)
            del item

    def clear_queue(self):
        self.current = None
        self.queue.clear()
        self.items.clear()
        self.pending.clear()

    def save(self):
        if not self.current:
            return
        try:
            if any(job.isRunning() and str(job.path) == self.current for job in self.jobs):
                raise ValueError('Várd meg a felismerés befejezését.')
            data = self.contract_fields()
            data.validate()
            if not self.confirm.isChecked():
                raise ValueError('Mentés előtt ellenőrizd és hagyd jóvá az adatokat.')
            filename = self.filename.text().strip()
            from .core import parse_filename
            parsed = parse_filename(filename)
            if (parsed.code, parsed.annex, parsed.date) != (data.code, data.annex, data.filename()[-12:-4]):
                raise ValueError('A fájlnév kódja, melléklete vagy dátuma eltér a mezőktől.')
            if Path(filename).name != filename or '/' in filename or '\\' in filename or ':' in filename:
                raise ValueError('A fájlnév nem tartalmazhat elérési utat.')
            folder = Path(self.folder.text())
            if not self.folder.text() or not folder.is_dir():
                raise ValueError('Válassz elérhető mentési mappát.')
            target = folder / filename
            if target.exists():
                W.QMessageBox.information(self, 'Névütközés', 'A célfájl már létezik. Adj meg másik fájlnevet, vagy hagyd ki a dokumentumot. Felülírás nem történik.')
                return
            duplicate = self.store.duplicate(digest(self.current))
            allow = False
            if duplicate:
                allow = W.QMessageBox.question(self, 'Duplikátum', 'Azonos tartalom már szerepel a nyilvántartásban. Új másolatot szeretnél menteni?', W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No) == W.QMessageBox.Yes
                if not allow:
                    return
            save_copy(self.current, target, self.store, allow)
            self.store.provider(data.code, data.provider, data.short)
            self.store.set_setting('folder', str(folder))
            self.items[self.current]['state'] = 'Kész'
            self.items[self.current]['item'].setText(Path(self.current).name + ' — Kész')
            self.statusBar().showMessage('Másolat mentve: ' + str(target))
            if self.next_check.isChecked():
                self.next_item()
        except Exception as error:
            self.error(error)

    def refresh(self):
        if not hasattr(self, 'table'):
            return
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        folder = self.folder.text()
        if not folder:
            return
        try:
            for path in sorted(Path(folder).rglob('*')):
                if path.suffix.lower() != '.pdf' or not path.is_file():
                    continue
                try:
                    data = parse_filename(path.name)
                except ValueError:
                    data = Contract(provider='Nem értelmezhető fájlnév')
                row = self.table.rowCount()
                self.table.insertRow(row)
                values = [path.name, data.code, data.provider, data.annex, data.date, self.store.status(path)[0]]
                for col, value in enumerate(values):
                    cell = W.QTableWidgetItem(value)
                    cell.setData(QtCore.Qt.UserRole, str(path))
                    self.table.setItem(row, col, cell)
            self.table.setSortingEnabled(True)
            self.filter_rows()
            self.statusBar().showMessage(f'{self.table.rowCount()} szerződés')
        except Exception as error:
            self.error(error)

    def reset_filter(self):
        self.search.clear()
        self.annex_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)

    def filter_rows(self):
        for row in range(self.table.rowCount()):
            values = [self.table.item(row, col).text() for col in range(6)]
            visible = self.search.text().casefold() in ' '.join(values).casefold()
            visible &= self.annex_filter.currentIndex() == 0 or values[3] == self.annex_filter.currentText()
            visible &= self.status_filter.currentIndex() == 0 or values[5] == self.status_filter.currentText()
            self.table.setRowHidden(row, not visible)

    def selected_path(self):
        row = self.table.currentRow()
        return self.table.item(row, 0).data(QtCore.Qt.UserRole) if row >= 0 else None

    def select_contract(self):
        path = self.selected_path()
        if path:
            status, timestamp = self.store.status(path)
            self.details.setText(path + '\nÁllapot: ' + status + ('\nFeltöltve: ' + timestamp if timestamp else ''))
            self.upload_state.setCurrentText(status)
            self.browse_preview.open(path)

    def mark(self):
        path = self.selected_path()
        if path:
            try:
                self.store.mark(path, self.upload_state.currentText())
                self.table.item(self.table.currentRow(), 5).setText(self.upload_state.currentText())
                self.select_contract()
                self.filter_rows()
            except Exception as error:
                self.error(error)

    def open_external(self):
        path = self.selected_path()
        if path:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))

    def open_folder(self):
        path = self.selected_path()
        if path:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(Path(path).parent)))

    def closeEvent(self, event):
        if any(job.isRunning() for job in self.jobs):
            self.error('A felismerés még fut. A bezárás előtt várd meg a befejezését.')
            event.ignore()
            return
        self.store.set_setting('folder', self.folder.text())
        self.store.set_setting('view', self.tabs.currentIndex())
        self.store.set_setting('geometry', bytes(self.saveGeometry().toBase64()).decode())
        self.store.set_setting('scan', bytes(self.scan_split.saveState().toBase64()).decode())
        self.store.set_setting('browse', bytes(self.browse_split.saveState().toBase64()).decode())
        self.store.db.close()
        self.staging.cleanup()
        event.accept()


def main():
    app = W.QApplication(sys.argv)
    app.setOrganizationName('NEAKSzerzodesRendezo')
    app.setApplicationName('OtthonapolasiSzerzodeskezelo')
    app.setStyle('Fusion')
    app.setStyleSheet('QGroupBox {font-weight:bold; margin-top:12px;} QGroupBox::title {subcontrol-origin:margin;} QPushButton {padding:7px;} QLineEdit,QComboBox {padding:5px;}')
    window = Window()
    window.showMaximized()
    sys.exit(app.exec_())

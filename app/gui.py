import base64
import hashlib
import math
import json
import os
from pathlib import Path
import sys
import tempfile
from PyQt5 import QtCore, QtGui, QtWidgets as W
import pypdfium2 as pdfium
from .core import Contract, Store, STATUSES, extract_contract, parse_filename, save_copy, digest, available_years
from .documents import recognize, import_files
from .pdf_ops import PDF_LOCK, write_rotated, replace_rotated
from .theme import apply_theme, icon, application_icon, CrystalPanel, CrystalStatusBar, CrystalHeader, STATE_ICONS


class Worker(QtCore.QThread):
    result = QtCore.pyqtSignal(object, object, str, object)

    def __init__(self, path, providers, automatic=True, rotations=None, manual=None, token=None):
        super().__init__()
        self.path, self.providers = path, providers
        self.token = token
        self.automatic, self.rotations, self.manual = automatic, rotations or {}, manual or {}

    def run(self):
        try:
            result = recognize(self.path, self.automatic, detailed=True, initial_rotations=self.rotations)
            data = extract_contract(result.text, self.providers)
            data.warnings.extend(result.warnings)
            error = '\n'.join(message for message in result.warnings if 'feldolgozási hibája' in message)
            self.result.emit(self.path, data, error, {'rotations': result.rotations, 'manual': self.manual, 'token': self.token})
        except Exception as error:
            self.result.emit(self.path, Contract(warnings=[str(error)]), str(error), {'token': self.token})


class PathLabel(W.QLabel):
    """Read-only, elided informational path with a full-path tooltip."""
    def __init__(self):
        super().__init__()
        self.full_path = ''
        self.setMinimumWidth(80)
        self.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Preferred)

    def setText(self, text):
        self.full_path = str(text)
        self.setToolTip(self.full_path)
        self.update_text()

    def text(self):
        return self.full_path

    def update_text(self):
        super().setText(self.fontMetrics().elidedText(self.full_path or 'Nincs beállítva', QtCore.Qt.ElideMiddle, max(80,self.width())))

    def resizeEvent(self, event):
        self.update_text()
        super().resizeEvent(event)


class QueueDelegate(W.QStyledItemDelegate):
    phase = 0

    def sizeHint(self,option,index):
        return QtCore.QSize(280,36)

    def paint(self,painter,option,index):
        state=index.data(QtCore.Qt.UserRole+1) or 'Várakozik'
        path=index.data(QtCore.Qt.UserRole) or ''
        opt=W.QStyleOptionViewItem(option);self.initStyleOption(opt,index);opt.text='';opt.icon=QtGui.QIcon()
        style=opt.widget.style() if opt.widget else W.QApplication.style()
        style.drawControl(W.QStyle.CE_ItemViewItem,opt,painter,opt.widget)
        selected=bool(opt.state & W.QStyle.State_Selected)
        painter.save()
        if selected and state=='Feldolgozás':
            painter.fillRect(opt.rect,QtGui.QColor('#b8dcff'))
        icon('pdf').paint(painter,QtCore.QRect(opt.rect.x()+5,opt.rect.y()+9,18,18))
        state_width=min(166,max(125,opt.rect.width()//2))
        split=opt.rect.right()-state_width
        painter.setPen(QtCore.Qt.white if selected and state!='Feldolgozás' else QtGui.QColor('#18354e'))
        painter.setFont(opt.font)
        filename=QtGui.QFontMetrics(opt.font).elidedText(Path(path).name,QtCore.Qt.ElideMiddle,max(20,split-opt.rect.x()-30))
        painter.drawText(QtCore.QRect(opt.rect.x()+29,opt.rect.y(),max(20,split-opt.rect.x()-30),opt.rect.height()),QtCore.Qt.AlignVCenter,filename)
        state_icon=icon(STATE_ICONS.get(state,'unknown'))
        if state=='Feldolgozás':
            painter.save();painter.translate(split+9,opt.rect.center().y());painter.rotate(self.phase*22.5)
            state_icon.paint(painter,QtCore.QRect(-8,-8,16,16));painter.restore()
        else:state_icon.paint(painter,QtCore.QRect(split,opt.rect.y()+10,16,16))
        font=QtGui.QFont(opt.font);font.setBold(state=='Feldolgozás');painter.setFont(font)
        if state=='Feldolgozás':
            intensity=int(18*(1+math.sin(self.phase*math.pi/8)))
            painter.setPen(QtGui.QColor(0,55+intensity,175+intensity))
        elif not selected:
            painter.setPen(QtGui.QColor('#247237' if state in ('Felismerve','Kész') else '#4a586a'))
        text=QtGui.QFontMetrics(font).elidedText(state,QtCore.Qt.ElideRight,state_width-22)
        painter.drawText(QtCore.QRect(split+22,opt.rect.y(),state_width-22,opt.rect.height()),QtCore.Qt.AlignVCenter,text)
        painter.restore()


class SettingsDialog(W.QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Beállítások')
        self.resize(650,360)
        layout = W.QVBoxLayout(self)
        files = W.QGroupBox('Fájlkezelés')
        row = W.QHBoxLayout(files)
        self.folder = W.QLineEdit(store.setting('folder'))
        self.folder.setPlaceholderText('Meghajtóbetűjeles vagy UNC-elérési út')
        row.addWidget(self.folder)
        browse = W.QPushButton('Tallózás…')
        browse.clicked.connect(self.browse)
        row.addWidget(browse)
        layout.addWidget(files)
        pdf = W.QGroupBox('PDF-megjelenítés')
        form = W.QFormLayout(pdf)
        self.view = W.QComboBox()
        self.view.addItems(['Oldalszélesség', '100%'])
        self.view.setCurrentText(store.setting('pdf_view','Oldalszélesség'))
        form.addRow('Alapértelmezett nézet', self.view)
        self.auto_preview = W.QCheckBox('Automatikus tájolás alkalmazása a betekintőben')
        self.auto_preview.setChecked(store.setting('auto_preview','1')=='1')
        form.addRow(self.auto_preview)
        layout.addWidget(pdf)
        ocr = W.QGroupBox('OCR')
        row = W.QVBoxLayout(ocr)
        self.auto_ocr = W.QCheckBox('Automatikus tájolásfelismerés')
        self.auto_ocr.setChecked(store.setting('auto_ocr','1')=='1')
        row.addWidget(self.auto_ocr)
        layout.addWidget(ocr)
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Save | W.QDialogButtonBox.Cancel)
        buttons.button(W.QDialogButtonBox.Save).setText('Mentés')
        buttons.button(W.QDialogButtonBox.Cancel).setText('Mégse')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse(self):
        path = W.QFileDialog.getExistingDirectory(self, 'Szerződésmappa kiválasztása', self.folder.text())
        if path:
            self.folder.setText(path)

    def apply(self, store):
        folder = self.folder.text().strip()
        if folder and not Path(folder).is_dir():
            raise ValueError('A megadott célmappa nem érhető el.')
        with store.db:
            for key, value in [('folder',folder), ('pdf_view',self.view.currentText()),
                               ('auto_preview','1' if self.auto_preview.isChecked() else '0'),
                               ('auto_ocr','1' if self.auto_ocr.isChecked() else '0')]:
                store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,value))


class Preview(W.QWidget):
    changed = QtCore.pyqtSignal()
    rotation_save = QtCore.pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.document = None
        self.path = None
        self.state = {'auto': {}, 'manual': {}}
        self.apply_auto = True
        self.index = 0
        self.scale = 1.0
        self.fit = True
        outer = W.QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        panel = CrystalPanel('PDF-betekintő')
        outer.addWidget(panel)
        layout = W.QVBoxLayout(panel)
        navigation = W.QToolBar()
        navigation.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        navigation.setIconSize(QtCore.QSize(24,24))
        for key,label,callback in [('previous','Előző oldal',lambda:self.turn(-1)),('next','Következő oldal',lambda:self.turn(1)),
                                   ('zoom_out','Kicsinyítés',lambda:self.zoom(.8)),('zoom_in','Nagyítás',lambda:self.zoom(1.25)),
                                   ('fit','Oldalszélesség',self.fit_width)]:
            action=navigation.addAction(icon(key),label,callback);action.setToolTip(label)
        self.counter = W.QLabel('0 / 0')
        navigation.addWidget(self.counter)
        layout.addWidget(navigation)
        rotation_bar = W.QToolBar()
        rotation_bar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        rotation_bar.setIconSize(QtCore.QSize(24,24))
        for key,label,callback in [('rotate_left','Forgatás\nbalra',lambda:self.rotate(-90)),
                                   ('rotate_right','Forgatás\njobbra',lambda:self.rotate(90)),
                                   ('save_rotation','Forgatás\nmentése',lambda:self.rotation_save.emit(self))]:
            action_item=rotation_bar.addAction(icon(key),label,callback)
            action_item.setToolTip(label.replace('\n',' '))
            if key=='save_rotation':
                self.rotation_save_action=action_item
                self.rotation_save_action.setEnabled(False)
        layout.addWidget(rotation_bar)
        self.scroll = W.QScrollArea()
        self.label = W.QLabel('Válassz dokumentumot')
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.scroll.setWidget(self.label)
        layout.addWidget(self.scroll)

    def rotation_map(self):
        keys = set(self.state['auto']) | set(self.state['manual'])
        return {index: ((self.state['auto'].get(index,0) if self.apply_auto else 0)
                        + self.state['manual'].get(index,0)) % 360 for index in keys}

    def rotate(self, angle):
        if self.document:
            self.state['manual'][self.index] = (self.state['manual'].get(self.index,0)+angle)%360
            self.render()

    def clear(self):
        with PDF_LOCK:
            if self.document:
                self.document.close()
        self.document = None
        self.path = None
        self.rotation_save_action.setEnabled(False)
        self.label.clear()
        self.label.setText('Válassz dokumentumot')
        self.label.adjustSize()
        self.counter.setText('0 / 0')
        self.index = 0
        self.state = {'auto': {}, 'manual': {}}
        self.changed.emit()

    def open(self, path, state=None):
        self.clear()
        self.path = str(path)
        self.state = state if state is not None else {'auto': {}, 'manual': {}}
        self.index = 0
        try:
            with PDF_LOCK:
                content = Path(path).read_bytes()
                self.document = pdfium.PdfDocument(content)
            self.fingerprint = hashlib.sha256(content).hexdigest()
            self.rotation_save_action.setEnabled(True)
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
            with PDF_LOCK:
                page = self.document[self.index]
                try:
                    angle = self.rotation_map().get(self.index,0)
                    width = page.get_height() if angle in (90,270) else page.get_width()
                    scale = max(.1, (self.scroll.viewport().width()-24)/width) if self.fit else self.scale
                    self.scale = scale
                    bitmap = page.render(scale=scale,rotation=angle)
                    try:
                        image = bitmap.to_pil().convert('RGB')
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            data = image.tobytes()
            qimage = QtGui.QImage(data, image.width, image.height, image.width*3, QtGui.QImage.Format_RGB888).copy()
            self.label.setPixmap(QtGui.QPixmap.fromImage(qimage))
            self.label.resize(image.width,image.height)
            self.counter.setText(f'{self.index+1} / {len(self.document)}')
            self.changed.emit()
        except Exception as error:
            self.label.setText(str(error))


class DateItem(W.QTableWidgetItem):
    """Display Hungarian dates; sort by an actual QDate, never by label text."""
    def __init__(self, compact):
        self.date = QtCore.QDate.fromString(compact,'yyyyMMdd')
        super().__init__(self.date.toString('yyyy.MM.dd.') if self.date.isValid() else '')
        self.setData(QtCore.Qt.UserRole+2,self.date)

    def __lt__(self, other):
        value = other.data(QtCore.Qt.UserRole+2)
        right = value.toJulianDay() if isinstance(value,QtCore.QDate) and value.isValid() else 0
        return (self.date.toJulianDay() if self.date.isValid() else 0) < right


class Window(W.QMainWindow):
    ole_files = QtCore.pyqtSignal(object, object)

    def __init__(self, data_dir=None):
        super().__init__()
        apply_theme(W.QApplication.instance())
        self.setWindowIcon(application_icon())
        root = Path(data_dir) if data_dir else Path(QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppLocalDataLocation))
        root.mkdir(parents=True, exist_ok=True)
        self.store = Store(root / 'contracts.sqlite3')
        self.staging = tempfile.TemporaryDirectory(prefix='neak-import-')
        self.jobs = []
        self.items = {}
        self.pending = []
        self.current = None
        self.session_id = 0
        self.item_serial = 0
        self.loading = False
        self.rotation_states = {}
        self.setWindowTitle('Otthonápolási szerződéskezelő – v0.2.0')
        self.resize(1500, 900)
        self.setAcceptDrops(True)
        self.tabs = W.QTabWidget()
        self.tabs.setElideMode(QtCore.Qt.ElideNone)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        self.setCentralWidget(self.tabs)
        self.create_actions()
        self.scan_page()
        self.browse_page()
        self.setup_chrome()
        self.native_drops = None
        self.native_drop_error = ''
        self.ole_files.connect(self.receive_ole_files, QtCore.Qt.QueuedConnection)
        if os.name == 'nt' and W.QApplication.platformName() == 'windows':
            from .windows_drop import NativeDrops
            try:
                self.native_drops = NativeDrops([self.inbox, self.queue.viewport()],
                                                self.staging.name, self.ole_files.emit)
            except Exception as error:
                self.native_drop_error = str(error)
                self.setAcceptDrops(True)
                message = ('Az Outlook-behúzás nem inicializálható. Az Outlookot és ezt a programot '
                           'is normál jogosultsággal indítsd. Részletek: ' + str(error))
                QtCore.QTimer.singleShot(0, lambda message=message: self.error(message))
        else:
            self.setAcceptDrops(True)
        self.tabs.currentChanged.connect(self.view_changed)
        self.statusBar().showMessage('Kész – minden feldolgozás helyben történik')
        self.apply_settings()
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
            QtCore.QTimer.singleShot(200, self.show_settings)

    def create_actions(self):
        self.actions={}
        self.action_buttons={}
        definitions=[
            ('add','Hozzáadás','add','add_dialog','Ctrl+O'),
            ('remove','Törlés','remove','remove_current','Delete'),
            ('clear','Lista ürítése','clear','clear_queue',''),
            ('retry','Felismerés\nújra','retry','rerun','Ctrl+R'),
            ('skip','Kihagyás','skip','next_item',''),
            ('save','Mentés és\nkövetkező','save','save','Ctrl+S'),
            ('pdf','PDF megnyitása','pdf','open_external',''),
            ('browse','Szerződések\ntallózása','browse','show_browse',''),
            ('settings','Beállítások','settings','show_settings',''),
            ('help','Súgó / Névjegy','help','show_about','F1'),
            ('refresh','Frissítés','refresh','refresh','F5'),
            ('reset_filter','Szűrés törlése','reset_filter','reset_filter',''),
            ('folder','Mappa megnyitása','folder','open_folder',''),
            ('mark','Állapot mentése','ready','mark',''),
            ('mark_uploaded','Megjelölés feltöltöttként','ready','mark_uploaded',''),
            ('providers','Szolgáltatói törzsadatok','document','edit_providers',''),
        ]
        for key,label,art,method,shortcut in definitions:
            action=W.QAction(icon(art),label,self)
            action.setToolTip(label.replace('\n',' '))
            action.setStatusTip(label.replace('\n',' '))
            action.triggered.connect(lambda checked=False,method=method:getattr(self,method)())
            if shortcut:action.setShortcut(shortcut)
            action.setEnabled(key in ('add','browse','settings','help','providers'))
            self.actions[key]=action
        self.button_actions={method:key for key,_,_,method,_ in definitions}

    def setup_chrome(self):
        menus=[('Fájl',['add','pdf','folder']),('Feldolgozás',['remove','clear','retry','skip','save']),
               ('Szerződések',['browse','refresh','reset_filter','mark_uploaded']),
               ('Nézet',['browse']),('Eszközök',['settings','providers']),('Súgó',['help'])]
        for title,keys in menus:
            menu=self.menuBar().addMenu(title)
            for key in keys:menu.addAction(self.actions[key])
        self.main_toolbar=W.QToolBar('Fő műveletek',self)
        self.main_toolbar.setObjectName('mainToolbar')
        self.main_toolbar.setMovable(False);self.main_toolbar.setFloatable(False)
        self.main_toolbar.setIconSize(QtCore.QSize(32,32))
        self.main_toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.addToolBar(self.main_toolbar)
        for key in ['add','remove','clear',None,'retry','skip','save',None,'pdf','browse',None,'settings','help']:
            if key is None:self.main_toolbar.addSeparator()
            else:self.main_toolbar.addAction(self.actions[key])
        self.setStatusBar(CrystalStatusBar(self))
        self.update_actions()

    def show_browse(self):
        self.tabs.setCurrentIndex(1)

    def mark_uploaded(self):
        self.mark_path(self.selected_path(),'Feltöltve')

    def show_about(self):
        W.QMessageBox.about(self,'Otthonápolási szerződéskezelő – Névjegy',
            'Otthonápolási szerződéskezelő v0.2.0\n\n'
            'Helyi, offline OCR és PDF-kezelés. A program nem tölt fel az ePénzbe.\n'
            'Dokumentumok: PDF, mentett MSG/EML és klasszikus Outlook behúzás.\n'
            'Állapotot a szerződéslistában jobb kattintással is módosíthatsz.\n\n'
            'Ikonok: Crystal Clear – Everaldo Coelho; PDF: KDE Crystal SVG – KDE Artists.\n'
            'Licencek és ikon-hozzárendelések: THIRD_PARTY_LICENSES.md, assets/licenses.\n'
            'Windows 10 1607 célgépes teszt: még nem igazolt.')

    def update_actions(self):
        if not hasattr(self,'table') or not hasattr(self,'actions'):
            return
        scan=self.tabs.currentIndex()==0
        entry=self.items.get(self.current)
        selected=self.selected_path() if not scan else self.current
        enabled={'add':scan,'remove':scan and bool(entry),'clear':scan and bool(self.items),
                 'retry':scan and bool(entry) and entry['state']!='Feldolgozás',
                 'skip':scan and bool(self.items),
                 'save':scan and bool(entry) and entry['state'] not in ('Várakozik','Feldolgozás'),
                 'pdf':bool(selected),'browse':True,'settings':True,'help':True,'providers':True,
                 'refresh':not scan,'reset_filter':not scan,'folder':not scan and bool(selected),
                 'mark':not scan and bool(selected),'mark_uploaded':not scan and bool(selected)}
        for key,value in enabled.items():self.actions[key].setEnabled(bool(value))
        if isinstance(self.statusBar(),CrystalStatusBar):
            if scan:
                page=self.scan_preview
                text=f'Dokumentum: {self.queue.currentRow()+1 if entry else 0} / {self.queue.count()}  |  Oldal: {page.index+1 if page.document else 0} / {len(page.document) if page.document else 0}'
                state=entry['state'] if entry else 'Kész'
            else:
                text=Path(selected).name if selected else ''
                state=self.store.status(selected)[0] if selected else 'Kész'
            self.statusBar().set_info(text)
            self.statusBar().state_icon=STATE_ICONS.get(state,'ready')
            self.statusBar().update()

    def button(self,text,callback,layout):
        button=W.QPushButton(text)
        button.setIconSize(QtCore.QSize(24,24))
        key=self.button_actions.get(callback.__name__)
        if key:
            action=self.actions[key]
            button.setProperty('actionKey',key)
            def sync():
                button.setIcon(action.icon());button.setEnabled(action.isEnabled());button.setToolTip(action.toolTip())
            action.changed.connect(sync);sync()
            button.clicked.connect(action.trigger)
        else:button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def panel(self,title):
        box=CrystalPanel(title)
        return box,W.QVBoxLayout(box)

    def scan_page(self):
        self.scan_split = W.QSplitter()
        self.tabs.addTab(self.scan_split,icon('pdf'),'Szkennelések feldolgozása')
        self.tabs.setIconSize(QtCore.QSize(24,24))
        box, layout = self.panel('Beérkezett dokumentumok')
        self.inbox = box
        instruction = W.QLabel('Húzz ide PDF-, MSG- vagy EML-fájlokat\nEgyszerre több dokumentum is hozzáadható.')
        instruction.setWordWrap(True)
        instruction.setToolTip(instruction.text())
        layout.addWidget(instruction)
        header=W.QFrame();header.setObjectName('queueHeader')
        headings=W.QHBoxLayout(header);headings.setContentsMargins(5,1,5,1)
        headings.addWidget(W.QLabel('Fájlnév'),1)
        state_heading=W.QLabel('Állapot');state_heading.setFixedWidth(154)
        headings.addWidget(state_heading);layout.addWidget(header)
        self.queue = W.QListWidget()
        self.queue_delegate = QueueDelegate(self.queue)
        self.queue.setItemDelegate(self.queue_delegate)
        self.queue.setAlternatingRowColors(True)
        self.pulse = QtCore.QTimer(self)
        self.pulse.setInterval(180)
        self.pulse.timeout.connect(self.animate_processing)
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
        self.filename.setObjectName("proposedFilename")
        form.addRow('Javasolt fájlnév', self.filename)
        self.folder = PathLabel()
        self.folder.setObjectName("targetPath")
        form.addRow('Mentési mappa', self.folder)
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
        layout.addLayout(bar)
        self.save_button = self.button('Mentés és következő',self.save,layout)
        self.save_button.setEnabled(False)
        self.save_button.setObjectName("primarySave")
        self.scan_split.addWidget(box)
        self.scan_preview = Preview()
        self.scan_preview.rotation_save.connect(self.save_rotation)
        self.scan_preview.changed.connect(self.update_actions)
        self.scan_split.addWidget(self.scan_preview)
        self.scan_split.setSizes([350, 450, 650])

    def browse_page(self):
        self.browse_split = W.QSplitter()
        self.tabs.addTab(self.browse_split,icon('browse'),'Szerződések tallózása')
        box, layout = self.panel('Szűrés és csoportosítás')
        self.search = W.QLineEdit()
        self.search.setPlaceholderText('NEAK-kód, szolgáltató, fájlnév…')
        self.search.textChanged.connect(self.filter_rows)
        layout.addWidget(W.QLabel('Keresett szöveg:'))
        layout.addWidget(self.search)
        layout.addWidget(W.QLabel('Év:'))
        self.year_filter = W.QComboBox()
        self.year_filter.setToolTip('Hatályosság kezdőéve a fájlnév alapján')
        self.year_filter.currentIndexChanged.connect(self.filter_rows)
        layout.addWidget(self.year_filter)
        self.refresh_years()
        self.year_timer = QtCore.QTimer(self)
        self.year_timer.setInterval(60000)
        self.year_timer.timeout.connect(self.refresh_years)
        self.year_timer.start()
        layout.addWidget(W.QLabel('Melléklet:'))
        self.annex_filter = W.QComboBox()
        self.annex_filter.addItems(['Összes melléklet', 'IX-1', 'IX-2', 'IX-3'])
        self.annex_filter.currentIndexChanged.connect(self.filter_rows)
        layout.addWidget(self.annex_filter)
        layout.addWidget(W.QLabel('ePénz-állapot:'))
        self.status_filter = W.QComboBox()
        self.status_filter.addItems(['Összes állapot'] + list(STATUSES))
        self.status_filter.currentIndexChanged.connect(self.filter_rows)
        layout.addWidget(self.status_filter)
        layout.addStretch()
        self.button('Frissítés', self.refresh, layout)
        self.button('Szűrés törlése', self.reset_filter, layout)
        self.browse_split.addWidget(box)
        middle = W.QSplitter(QtCore.Qt.Vertical)
        box, layout = self.panel('Szerződések listája')
        self.table = W.QTableWidget(0, 6)
        self.table.setHorizontalHeader(CrystalHeader(self.table))
        self.table.horizontalHeader().setToolTip('A fejléc kattintásával rendezhető.')
        self.table.setHorizontalHeaderLabels(['Fájlnév', 'NEAK-kód', 'Szolgáltató', 'Melléklet', 'Hatályosság kezdete', 'ePénz'])
        self.table.setAlternatingRowColors(True)
        self.table.setIconSize(QtCore.QSize(16,16))
        self.table.setSelectionBehavior(W.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(W.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.select_contract)
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_status_menu)
        header=self.table.horizontalHeader()
        header.setMinimumSectionSize(65)
        header.setSectionResizeMode(0,W.QHeaderView.Stretch)
        for column,width in [(1,84),(2,122),(3,80),(4,115),(5,140)]:
            header.setSectionResizeMode(column,W.QHeaderView.Interactive)
            header.resizeSection(column,width)
        layout.addWidget(self.table)
        middle.addWidget(box)
        box, layout = self.panel('Kijelölt szerződés')
        body=W.QHBoxLayout()
        form=W.QFormLayout()
        self.contract_details={}
        for key,label in [('path','Fájl elérési útja:'),('code','NEAK-kód:'),('provider','Szolgáltató:'),
                           ('annex','Melléklet:'),('date','Hatályosság kezdete:')]:
            field=W.QLineEdit();field.setReadOnly(True)
            self.contract_details[key]=field;form.addRow(label,field)
        self.details=W.QLabel('Válassz szerződést');self.details.setWordWrap(True)
        form.addRow(self.details)
        self.upload_state=W.QComboBox();self.upload_state.addItems(STATUSES)
        form.addRow('Állapot beállítása:',self.upload_state)
        body.addLayout(form,1)
        operations=W.QVBoxLayout()
        hint=W.QLabel('Jobb kattintás:\nállapot módosítása');hint.setWordWrap(True);operations.addWidget(hint)
        self.button('Megjelölés feltöltöttként',self.mark_uploaded,operations)
        self.button('Állapot mentése',self.mark,operations)
        self.button('PDF megnyitása',self.open_external,operations)
        self.button('Mappa megnyitása',self.open_folder,operations)
        operations.addStretch();body.addLayout(operations)
        layout.addLayout(body)
        middle.addWidget(box)
        self.browse_split.addWidget(middle)
        self.browse_preview = Preview()
        self.browse_preview.rotation_save.connect(self.save_rotation)
        self.browse_preview.changed.connect(self.update_actions)
        self.browse_split.addWidget(self.browse_preview)
        self.browse_split.setSizes([240, 800, 640])

    def view_changed(self, index):
        if index == 1:
            self.refresh()
        self.update_actions()

    def error(self, error):
        W.QMessageBox.warning(self, 'Ellenőrizendő', str(error))

    def rotation_state(self, path):
        return self.rotation_states.setdefault(str(path), {'auto': {}, 'manual': {}})

    def apply_settings(self):
        self.folder.setText(self.store.setting('folder'))
        for preview in (self.scan_preview, self.browse_preview):
            preview.apply_auto = self.store.setting('auto_preview','1') == '1'
            preview.fit = self.store.setting('pdf_view','Oldalszélesség') == 'Oldalszélesség'
            if not preview.fit:
                preview.scale = 1.0
            preview.render()

    def show_settings(self):
        dialog = SettingsDialog(self.store,self)
        while dialog.exec_() == W.QDialog.Accepted:
            try:
                dialog.apply(self.store)
                self.apply_settings()
                self.refresh()
                return
            except Exception as error:
                self.error(error)

    def choose_folder(self):
        self.show_settings()

    def save_rotation(self, preview):
        if not preview.path or not preview.document:
            return
        if preview is self.scan_preview:
            self.statusBar().showMessage('A forgatás a végleges másolat mentésekor kerül a PDF-be. A forrás változatlan.')
            return
        rotations = {key:value for key,value in preview.rotation_map().items() if value}
        if not rotations:
            return
        if any(job.isRunning() and str(job.path)==preview.path for job in self.jobs):
            self.error('Várd meg a dokumentum felismerésének befejezését.')
            return
        answer = W.QMessageBox.question(self,'Forgatás mentése',
            'A szerződéstári PDF tájolása megváltozik. Felülírod a kijelölt fájlt?',
            W.QMessageBox.Yes | W.QMessageBox.No,W.QMessageBox.No)
        if answer != W.QMessageBox.Yes:
            return
        try:
            path = preview.path
            replace_rotated(path,rotations,preview.fingerprint)
            state = self.rotation_state(path)
            state['auto'].clear()
            state['manual'].clear()
            for viewer in (self.scan_preview,self.browse_preview):
                if viewer.path == path:
                    page = viewer.index
                    viewer.open(path,state)
                    viewer.index = page
                    viewer.render()
            self.store.db.execute('UPDATE documents SET hash=? WHERE path=?',(digest(path),str(Path(path).absolute())))
            self.store.db.commit()
            self.statusBar().showMessage('A PDF forgatása mentve.')
        except Exception as error:
            self.error(error)

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
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()

    def dropEvent(self, event):
        self.add_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.setDropAction(QtCore.Qt.CopyAction)
        event.accept()

    def receive_ole_files(self, files, errors):
        self.add_files(files)
        if errors:
            self.error('\n'.join(str(error) for error in errors))

    def add_files(self, files):
        for file in files:
            try:
                paths = import_files([file], self.staging.name)
                for path in paths:
                    if str(path) in self.items:
                        continue
                    item = W.QListWidgetItem(icon('pdf'),path.name + ' — Várakozik')
                    item.setData(QtCore.Qt.UserRole, str(path))
                    self.queue.addItem(item)
                    self.item_serial += 1
                    self.items[str(path)] = {'item': item, 'data': Contract(), 'state': 'Várakozik', 'token': self.item_serial}
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
        state = self.rotation_state(path)
        rotations = {key: ((state['auto'].get(key,0) if self.store.setting('auto_preview','1')=='1' else 0)+state['manual'].get(key,0))%360
                     for key in set(state['auto']) | set(state['manual'])}
        worker = Worker(path, self.store.providers(), self.store.setting('auto_ocr','1')=='1',rotations,dict(state['manual']),
                        token=(self.session_id,self.items[path]['token']))
        self.set_queue_state(path,'Feldolgozás')
        self.pulse.start()
        worker.result.connect(self.recognized)
        worker.finished.connect(self.start_next)
        self.jobs.append(worker)
        worker.start()

    def set_queue_state(self, path, state):
        entry = self.items[path]
        entry['state'] = state
        entry['item'].setText(Path(path).name+' — '+state)
        entry['item'].setData(QtCore.Qt.UserRole+1,state)
        entry['item'].setToolTip(Path(path).name+' — '+state)
        self.update_save_enabled()
        self.show_scan_state()

    def animate_processing(self):
        active = [entry for entry in self.items.values() if entry['state']=='Feldolgozás']
        if not active:
            self.pulse.stop()
            return
        self.queue_delegate.phase = (self.queue_delegate.phase+1)%16
        for entry in active:
            self.queue.viewport().update(self.queue.visualItemRect(entry['item']))

    def recognized(self, path, data, error, metadata=None):
        path = str(path)
        if path not in self.items:
            return
        entry = self.items[path]
        metadata = metadata or {}
        token = metadata.get('token')
        if token is not None and token != (self.session_id,entry['token']):
            return
        entry['data'] = data
        state = self.rotation_state(path)
        manual = metadata.get('manual',{})
        suggestions = {index:(angle-manual.get(index,0))%360 for index,angle in metadata.get('rotations',{}).items()}
        # Keep explicit rotations made while this background job was running.
        for index in set(state['manual']) | set(manual):
            if state['manual'].get(index,0) != manual.get(index,0):
                suggestions[index] = state['auto'].get(index,0)
        state['auto'] = suggestions
        self.set_queue_state(path,'Feldolgozási hiba' if error else ('Ellenőrizendő' if data.warnings else 'Felismerve'))
        self.animate_processing()
        if self.current == path:
            self.load_fields(data)
            self.scan_preview.render()
        self.update_actions()

    def select_queue(self, item, previous):
        self.stash_fields()
        self.current = item.data(QtCore.Qt.UserRole) if item else None
        if self.current:
            self.load_fields(self.items[self.current]['data'])
            self.scan_preview.open(self.current,self.rotation_state(self.current))
        else:
            self.reset_scan_details()
        self.update_save_enabled()
        self.show_scan_state()

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
            if self.current not in self.pending:
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

    def show_scan_state(self):
        if self.tabs.currentIndex()!=0 or self.current not in self.items:return
        state=self.items[self.current]['state']
        messages={'Várakozik':'Feldolgozásra vár','Feldolgozás':'Feldolgozás…',
                  'Felismerve':'Feldolgozás kész – készen áll a mentésre',
                  'Ellenőrizendő':'A felismert adatok ellenőrzést igényelnek',
                  'Feldolgozási hiba':'Feldolgozási hiba – az adatok kézzel javíthatók',
                  'Kész':'A másolat mentve'}
        self.statusBar().showMessage(messages.get(state,state))

    def update_save_enabled(self):
        self.update_actions()

    def reset_scan_details(self):
        self.load_fields(Contract())
        self.filename.clear()
        self.warning.clear()
        self.confirm.setChecked(False)
        self.scan_preview.clear()
        self.scan_preview.scale = 1.0
        self.scan_preview.fit = self.store.setting('pdf_view','Oldalszélesség')=='Oldalszélesség'
        self.update_save_enabled()

    def clear_queue(self):
        # Invalidate results BEFORE changing widgets, including re-import of the
        # same pathname while an older worker is still finishing in the background.
        self.session_id += 1
        paths = list(self.items)
        self.current = None
        self.pending.clear()
        self.queue.clear()
        self.items.clear()
        for path in paths:
            self.rotation_states.pop(path,None)
        self.pulse.stop()
        self.reset_scan_details()
        self.statusBar().showMessage('A feldolgozási lista kiürítve.')

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
            state = self.rotation_state(self.current)
            rotations = {key: ((state['auto'].get(key,0) if self.store.setting('auto_preview','1')=='1' else 0)+state['manual'].get(key,0))%360
                         for key in set(state['auto']) | set(state['manual'])}
            if any(rotations.values()):
                handle, temporary = tempfile.mkstemp(suffix='.pdf',prefix='rotated-',dir=self.staging.name)
                os.close(handle)
                try:
                    write_rotated(self.current,temporary,rotations)
                    save_copy(temporary,target,self.store,allow)
                finally:
                    Path(temporary).unlink(missing_ok=True)
            else:
                save_copy(self.current, target, self.store, allow)
            self.store.provider(data.code, data.provider, data.short)
            self.store.set_setting('folder', str(folder))
            self.set_queue_state(self.current,'Kész')
            self.statusBar().showMessage('Másolat mentve: ' + str(target))
            if self.next_check.isChecked():
                self.next_item()
        except Exception as error:
            self.error(error)

    def refresh(self):
        if not hasattr(self, 'table'):
            return
        self.refresh_years()
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
                    cell = DateItem(data.date) if col==4 else W.QTableWidgetItem(value)
                    if col==0:cell.setIcon(icon('pdf'))
                    if col==5:cell.setIcon(icon(STATE_ICONS.get(value,'unknown')))
                    cell.setToolTip(str(path) if col==0 else value)
                    cell.setData(QtCore.Qt.UserRole, str(path))
                    self.table.setItem(row, col, cell)
            self.table.setSortingEnabled(True)
            self.filter_rows()
            if self.tabs.currentIndex()==1:
                self.statusBar().showMessage(f'{self.table.rowCount()} szerződés')
            elif not self.items:
                self.statusBar().showMessage('Kész – dokumentumok hozzáadására vár')
            self.update_actions()
        except Exception as error:
            self.error(error)

    def reset_filter(self):
        self.search.clear()
        self.annex_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.year_filter.setCurrentIndex(0)

    def refresh_years(self, year=None):
        options = ['Összes év'] + available_years(year)
        if [self.year_filter.itemText(i) for i in range(self.year_filter.count())] == options:
            return
        previous = self.year_filter.currentText()
        blocked = self.year_filter.blockSignals(True)
        self.year_filter.clear()
        self.year_filter.addItems(options)
        self.year_filter.setCurrentText(previous if previous in options else 'Összes év')
        self.year_filter.blockSignals(blocked)
        if hasattr(self,'table'):
            self.filter_rows()

    def filter_rows(self):
        if not hasattr(self,'table'):
            return
        for row in range(self.table.rowCount()):
            values = [self.table.item(row, col).text() for col in range(6)]
            visible = self.search.text().casefold() in ' '.join(values).casefold()
            visible &= self.annex_filter.currentIndex() == 0 or values[3] == self.annex_filter.currentText()
            visible &= self.status_filter.currentIndex() == 0 or values[5] == self.status_filter.currentText()
            date = self.table.item(row,4).data(QtCore.Qt.UserRole+2)
            if self.year_filter.currentIndex()>0:
                visible &= isinstance(date,QtCore.QDate) and date.isValid() and str(date.year())==self.year_filter.currentText()
            self.table.setRowHidden(row, not visible)

    def selected_path(self):
        row = self.table.currentRow()
        return self.table.item(row, 0).data(QtCore.Qt.UserRole) if row >= 0 else None

    def select_contract(self):
        path=self.selected_path()
        if path:
            status,timestamp=self.store.status(path)
            try:data=parse_filename(Path(path).name)
            except ValueError:data=Contract()
            known=self.store.db.execute('SELECT name FROM providers WHERE code=?',(data.code,)).fetchone()
            provider=known[0] if known and known[0] else data.provider
            values={'path':path,'code':data.code,'provider':provider,'annex':data.annex,
                    'date':QtCore.QDate.fromString(data.date,'yyyyMMdd').toString('yyyy.MM.dd.')}
            for key,value in values.items():
                self.contract_details[key].setText(value);self.contract_details[key].setToolTip(value)
            self.details.setText('ePénz: '+status+('\nFeltöltve: '+timestamp if timestamp else ''))
            self.upload_state.setCurrentText(status)
            self.browse_preview.open(path,self.rotation_state(path))
        else:
            for field in self.contract_details.values():field.clear()
            self.details.setText('Válassz szerződést')
        self.update_actions()

    def show_status_menu(self, position):
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        self.table.selectionModel().setCurrentIndex(
            self.table.model().index(index.row(),0),
            QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
        path = self.selected_path()  # Bind once; sorting/filtering cannot redirect the action.
        menu = W.QMenu(self.table)
        for label,status in [('Megjelölés feltöltöttként','Feltöltve'),
                             ('Nincs feltöltve','Nincs feltöltve'),
                             ('Ellenőrizendő','Ellenőrizendő'),('Ismeretlen','Ismeretlen')]:
            action = menu.addAction(icon(STATE_ICONS[status]),label)
            action.triggered.connect(lambda checked=False,path=path,status=status:self.mark_path(path,status))
        try:
            menu.exec_(self.table.viewport().mapToGlobal(position))
        finally:
            menu.deleteLater()

    def mark_path(self, path, status):
        if not path:
            return
        try:
            self.store.mark(path,status)
            sorting = self.table.isSortingEnabled()
            self.table.setSortingEnabled(False)
            try:
                for row in range(self.table.rowCount()):
                    if self.table.item(row,0).data(QtCore.Qt.UserRole)==path:
                        self.table.item(row,5).setText(status)
                        self.table.item(row,5).setIcon(icon(STATE_ICONS[status]))
                        break
            finally:
                self.table.setSortingEnabled(sorting)
            if self.selected_path()==path:
                self.select_contract()
            self.filter_rows()
        except Exception as error:
            self.error(error)

    def mark(self):
        self.mark_path(self.selected_path(),self.upload_state.currentText())

    def open_external(self):
        path = self.current if self.tabs.currentIndex()==0 else self.selected_path()
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
        if self.native_drops is not None:
            self.native_drops.close()
        self.pulse.stop()
        self.year_timer.stop()
        self.scan_preview.clear()
        self.browse_preview.clear()
        self.store.db.close()
        self.staging.cleanup()
        event.accept()


def main():
    W.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling,True)
    W.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps,True)
    if os.name=='nt':
        import ctypes
        shell=ctypes.WinDLL('shell32')
        shell.SetCurrentProcessExplicitAppUserModelID.argtypes=[ctypes.c_wchar_p]
        shell.SetCurrentProcessExplicitAppUserModelID('NEAK.OtthonapolasiSzerzodeskezelo')
    app=W.QApplication(sys.argv)
    app.setOrganizationName('NEAKSzerzodesRendezo')
    app.setApplicationName('OtthonapolasiSzerzodeskezelo')
    apply_theme(app)
    window=Window();window.showMaximized()
    sys.exit(app.exec_())

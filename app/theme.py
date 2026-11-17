"""Central Keramik-inspired blue/silver Qt 5 theme and licensed Crystal assets."""
from functools import lru_cache
from pathlib import Path
import json
import sys
from PyQt5 import QtCore, QtGui, QtWidgets as W


def asset_path(relative):
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
    return root/'assets'/relative


@lru_cache(None)
def catalog():
    return json.loads(asset_path('icons/catalog.json').read_text(encoding='utf-8'))


@lru_cache(None)
def icon(key):
    record=catalog()[key]
    root=asset_path('..').resolve()
    result=QtGui.QIcon(str(root/record['file']))
    if key=='pdf':
        for size in [16,22,32,48,64,128]:
            result.addFile(str(asset_path(f'icons/crystalsvg/cr{size}-mime-pdf.png')),QtCore.QSize(size,size))
    if result.isNull():
        raise RuntimeError('Hiányzó Crystal ikon: '+record['file'])
    return result


def application_icon():
    return QtGui.QIcon(str(asset_path('branding/application.ico')))


STYLESHEET='''
QMainWindow, QDialog {background:#e2eefb; color:#102b43;}
QWidget {font-family:"Segoe UI"; font-size:10pt;}
QLabel {background:transparent; color:#15334d;}
QMenuBar {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #f7fcff,stop:1 #b9d8f5); border-bottom:1px solid #7ca5d2; padding:2px;}
QMenuBar::item {padding:4px 10px; background:transparent;}
QMenuBar::item:selected,QMenu::item:selected {background:#2f8cdb;color:white;}
QMenu {background:#f4f9ff;border:1px solid #7d9cbd;padding:4px;}
QMenu::item {padding:7px 22px 7px 28px;}
QMenu::separator {height:1px;background:#a6c1db;margin:4px;}
QToolBar {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #e9f6ff,stop:0.44 #c4e4ff,stop:0.46 #a8d4f6,stop:1 #d9ecfb);border:1px solid #7da7cf;spacing:4px;padding:5px;}
QToolBar#mainToolbar {border-radius:4px;padding:5px 8px;}
QToolBar::separator {width:2px;background:#7da7cf;margin:5px 7px;}
QToolButton {border:1px solid transparent;border-radius:4px;padding:5px;color:#123451;}
QToolButton:hover {border:1px solid #4385be;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 white,stop:1 #b5dcff);}
QToolButton:pressed {background:#79b2e6;border:1px solid #2c659b;}
QToolButton:disabled {color:#8596a7;}
QPushButton {padding:7px 10px;border:1px solid #849ab4;border-radius:5px;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffffff,stop:0.48 #f1f5fb,stop:0.5 #dae5f2,stop:1 #bdcfe2);color:#143450;min-height:22px;}
QPushButton:hover {border-color:#317dc0;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 white,stop:0.48 #e7f5ff,stop:0.5 #b5dbfa,stop:1 #9dc9f0);}
QPushButton:pressed {background:#9fc7eb;border-color:#1f659f;}
QPushButton:disabled {color:#8a9aab;border-color:#bdcad8;background:#e5edf5;}
QPushButton#primarySave {font-weight:bold;border:2px solid #3887ce;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 white,stop:0.48 #e8f8ff,stop:1 #a4d8ff);}
QLineEdit,QComboBox,QPlainTextEdit {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 white,stop:1 #f3f8ff);border:1px solid #819fbe;border-radius:3px;padding:5px;color:#102a40;min-height:20px;selection-background-color:#277fd0;}
QLineEdit:focus,QComboBox:focus {border:1px solid #167bce;}
QLineEdit:read-only {background:#eaf2fa;color:#29435d;}
QLineEdit#proposedFilename {font-weight:bold;background:#fffde8;border:1px solid #cdbf66;}
QLabel#targetPath {background:#cce1f4;border:1px solid #91b4d6;border-radius:4px;padding:7px;}
QFrame#queueHeader {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 white,stop:1 #d7e3ef);border:1px solid #9aafc6;padding:6px;font-weight:bold;}
QListWidget,QTableWidget {background:white;alternate-background-color:#edf5fd;border:1px solid #8cabc9;border-radius:3px;gridline-color:#c4d6e7;selection-background-color:#338de0;selection-color:white;}
QListWidget::item {padding:3px;}
QListWidget::item:selected,QTableWidget::item:selected {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #86c6ff,stop:0.5 #459deb,stop:1 #1775cc);color:white;}
QHeaderView::section {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 white,stop:0.5 #e8eff7,stop:1 #ccd9e8);border:1px solid #a5b9cf;padding:7px;color:#15334c;font-weight:bold;}
QTabWidget::pane {border:1px solid #7ea9d4;border-radius:4px;background:#d7e8f9;top:-1px;}
QTabBar::tab {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #f6fbff,stop:0.45 #d7e9fa,stop:1 #b2cee9);border:1px solid #7e9fc3;border-top-left-radius:5px;border-top-right-radius:5px;padding:8px 16px;min-height:26px;margin-top:3px;color:#234d74;}
QTabBar::tab:selected {font-weight:bold;color:#003b7e;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 white,stop:1 #e1effb);border-bottom-color:#e1effb;}
QSplitter::handle {background:#b6d1e9;width:5px;height:5px;border:1px solid #edf6ff;}
QScrollArea {border:1px solid #8fabc5;background:#bdc9d4;}
QScrollBar:vertical {background:#e1ebf5;width:16px;}
QScrollBar::handle:vertical {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #eff7ff,stop:1 #9ebcda);min-height:24px;border:1px solid #8ba6c1;border-radius:3px;}
QStatusBar {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 white,stop:1 #c3e0fa);border:1px solid #7e9fc3;color:#064a86;font-weight:bold;min-height:28px;}
QStatusBar::item {border:0;}
QToolTip {background:#ffffe4;color:#19334c;border:1px solid #7b92a7;padding:4px;}
QCheckBox {spacing:7px;color:#15334d;}
QGroupBox {border:1px solid #91afd0;border-radius:4px;margin-top:18px;padding:10px;}
QGroupBox::title {subcontrol-origin:margin;background:#d0e5fa;padding:3px 8px;font-weight:bold;}
'''


def apply_theme(app):
    app.setStyle('Fusion')
    app.setFont(QtGui.QFont('Segoe UI',10))
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(application_icon())


PANEL_ICONS={'Beérkezett dokumentumok':'document','Felismert adatok':'document',
             'Szűrők és csoportosítás':'filter','Szűrés és csoportosítás':'filter',
             'Szerződések listája':'document','Kijelölt szerződés':'document',
             'PDF-betekintő':'pdf'}


class CrystalPanel(W.QGroupBox):
    def __init__(self,title,parent=None):
        super().__init__(title,parent)
        self.setContentsMargins(8,43,8,8)
        font=QtGui.QFont(self.font());font.setBold(True);font.setPointSizeF(11)
        self.setMinimumWidth(QtGui.QFontMetrics(font).horizontalAdvance(title)+64)
        self.header_icon=PANEL_ICONS.get(title,'document')

    def paintEvent(self,event):
        painter=QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        body=QtCore.QRectF(1,1,self.width()-2,self.height()-2)
        fill=QtGui.QLinearGradient(0,0,0,self.height());fill.setColorAt(0,QtGui.QColor('#edf7ff'));fill.setColorAt(1,QtGui.QColor('#d9e9fa'))
        painter.setBrush(fill);painter.setPen(QtGui.QPen(QtGui.QColor('#7fa8d0'),1));painter.drawRoundedRect(body,5,5)
        header=QtCore.QRectF(3,3,self.width()-6,33)
        gradient=QtGui.QLinearGradient(0,3,0,36)
        for stop,color in [(0,'#b2dfff'),(.12,'#75bef3'),(.48,'#2b91dc'),(.52,'#0877c6'),(1,'#0066b6')]:gradient.setColorAt(stop,QtGui.QColor(color))
        painter.setBrush(gradient);painter.setPen(QtGui.QColor('#5b9bd1'));painter.drawRoundedRect(header,4,4)
        icon(self.header_icon).paint(painter,QtCore.QRect(10,9,20,20))
        font=QtGui.QFont(self.font());font.setBold(True);font.setPointSizeF(11);painter.setFont(font)
        painter.setPen(QtGui.QColor('#135991'));painter.drawText(QtCore.QRect(38,5,self.width()-46,32),QtCore.Qt.AlignVCenter,self.title())
        painter.setPen(QtCore.Qt.white);painter.drawText(QtCore.QRect(38,4,self.width()-46,32),QtCore.Qt.AlignVCenter,self.title())


class CrystalStatusBar(W.QStatusBar):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.state_icon='ready'
        self.info=''
        self.setSizeGripEnabled(True)

    def showMessage(self,message,timeout=0):
        self.setToolTip(message+('\n'+self.info if self.info else ''))
        super().showMessage(message,timeout)

    def set_info(self,text):
        self.info=text
        self.setToolTip(self.currentMessage()+('\n'+text if text else ''))
        self.update()

    def paintEvent(self,event):
        painter=QtGui.QPainter(self)
        gradient=QtGui.QLinearGradient(0,0,0,self.height())
        gradient.setColorAt(0,QtGui.QColor('#ffffff'));gradient.setColorAt(1,QtGui.QColor('#bfddf8'))
        painter.fillRect(self.rect(),gradient)
        painter.setPen(QtGui.QColor('#7e9fc3'));painter.drawRect(self.rect().adjusted(0,0,-1,-1))
        icon(self.state_icon).paint(painter,QtCore.QRect(7,max(0,(self.height()-20)//2),20,20))
        painter.setFont(self.font());painter.setPen(QtGui.QColor('#064a86'))
        split=int(self.width()*.58)
        left=QtCore.QRect(35,0,max(0,split-43),self.height())
        right=QtCore.QRect(split,0,max(0,self.width()-split-20),self.height())
        metrics=painter.fontMetrics()
        painter.drawText(left,QtCore.Qt.AlignVCenter,metrics.elidedText(self.currentMessage(),QtCore.Qt.ElideMiddle,left.width()))
        painter.drawText(right,QtCore.Qt.AlignVCenter|QtCore.Qt.AlignRight,metrics.elidedText(self.info,QtCore.Qt.ElideMiddle,right.width()))


STATE_ICONS={'Várakozik':'waiting','Feldolgozás':'processing','Felismerve':'ready','Kész':'ready',
             'Ellenőrizendő':'warning','Feldolgozási hiba':'error','Feltöltve':'ready',
             'Nincs feltöltve':'error','Ismeretlen':'unknown'}


class CrystalHeader(W.QHeaderView):
    """Wrap the effective-date caption while keeping its exact model text."""
    def __init__(self,parent=None):
        super().__init__(QtCore.Qt.Horizontal,parent)
        self.setSectionsClickable(True)
        self.setSortIndicatorShown(True)
        self.setFixedHeight(46)

    def paintSection(self,painter,rect,logical):
        if not rect.isValid():return
        option=W.QStyleOptionHeader();self.initStyleOption(option)
        option.rect=rect;option.section=logical
        option.text=''
        self.style().drawControl(W.QStyle.CE_HeaderSection,option,painter,self)
        painter.save()
        font=QtGui.QFont(self.font());font.setBold(True);painter.setFont(font)
        painter.setPen(QtGui.QColor('#15334c'))
        text=str(self.model().headerData(logical,QtCore.Qt.Horizontal) or '')
        area=rect.adjusted(5,2,-5,-2)
        if self.sortIndicatorSection()==logical:
            area.adjust(0,0,-12,0)
            arrow=W.QStyleOptionHeader(option)
            arrow.rect=QtCore.QRect(rect.right()-13,rect.center().y()-5,10,10)
            arrow.sortIndicator=W.QStyleOptionHeader.SortDown if self.sortIndicatorOrder()==QtCore.Qt.AscendingOrder else W.QStyleOptionHeader.SortUp
            self.style().drawPrimitive(W.QStyle.PE_IndicatorHeaderArrow,arrow,painter,self)
        painter.drawText(area,QtCore.Qt.AlignCenter|QtCore.Qt.TextWordWrap,text)
        painter.restore()

"""Real Qt normal/maximized render checks at QT_SCALE_FACTOR 1/1.25/1.5."""
from pathlib import Path
import argparse
import os
import tempfile
from PyQt5 import QtCore, QtWidgets as W
from app.core import Store
from app.gui import Window
from app.theme import CrystalPanel,application_icon


def run(output):
    W.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling,True)
    W.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps,True)
    app=W.QApplication.instance() or W.QApplication([])
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='neak-visual-') as tmp:
        root=Path(tmp);store=Store(root/'contracts.sqlite3');store.set_setting('folder',str(root));store.db.close()
        window=Window(root)
        assert not window.windowIcon().isNull()
        assert {(size.width(),size.height()) for size in application_icon().availableSizes()}>={(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)}
        for maximized in [False,True]:
            if maximized:window.showMaximized()
            else:window.resize(1440,900);window.showNormal()
            app.processEvents()
            for page in [0,1]:
                window.tabs.setCurrentIndex(page);app.processEvents()
                assert window.tabs.elideMode()==QtCore.Qt.ElideNone
                for index in range(2):
                    width=window.tabs.tabBar().tabRect(index).width()
                    assert width>=window.tabs.fontMetrics().horizontalAdvance(window.tabs.tabText(index))+24
                for panel in window.findChildren(CrystalPanel):
                    assert panel.width()>=panel.minimumWidth()
                for action in window.main_toolbar.actions():
                    if action.isSeparator():continue
                    button=window.main_toolbar.widgetForAction(action)
                    assert not action.icon().isNull()
                    if button.isVisible():
                        required=max(button.fontMetrics().horizontalAdvance(line) for line in action.text().split('\n'))
                        assert button.width()>=required+6,(action.text(),button.width(),required)
                pixmap=window.grab();assert not pixmap.isNull()
                ratio=window.devicePixelRatioF()
                expected=float(os.environ.get('QT_SCALE_FACTOR','1'))
                assert abs(ratio-expected)<.02,(ratio,expected)
                assert abs(pixmap.width()-window.width()*ratio)<=2
                name=f"{'maximized' if maximized else 'normal'}-page{page}-scale{expected}.png"
                assert pixmap.save(str(output/name))
        window.close()
    print('PASS: actual themed Qt pages, normal/maximized, icons and full labels; scale='+os.environ.get('QT_SCALE_FACTOR','1'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='build/visual');args=parser.parse_args();run(args.output)

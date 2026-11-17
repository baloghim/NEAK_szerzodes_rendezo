import json
import gzip
import hashlib
from pathlib import Path
import pytest
from PIL import Image
from PyQt5 import QtCore,QtGui,QtWidgets as W
from app.gui import Window
from app.core import Store,Contract
from app.theme import icon,catalog,asset_path,application_icon,CrystalPanel,STYLESHEET
from test_rotation import make_pdf


def test_original_icon_files_and_licenses():
    root=Path(__file__).resolve().parents[1]
    assert len(catalog())>=25
    for key,record in catalog().items():
        path=root/record['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
        assert Image.open(path).width>=128
        assert record['license'].startswith('LGPL-2.1')
        assert '/blob/' in record['source'] and record['original']
        assert record['set']==('KDE Crystal SVG' if key=='pdf' else 'Crystal Clear')
        assert 'oxygen' not in record['source'].lower()
    assert b'<svg' in gzip.decompress(asset_path('icons/crystalsvg/crsc-mime-pdf.svgz').read_bytes())
    notice=asset_path('licenses/CrystalSVG-NOTICE.txt').read_text()
    assert 'all CrystalSVG images' in notice and 'NOTE THIS ADD-ON' in notice
    assert 'Everaldo Coelho' in asset_path('licenses/CrystalClear-README.txt').read_text()
    assert 'background:qlineargradient' in STYLESHEET


def test_application_ico_is_transparent_multisize_and_colorful():
    image=Image.open(asset_path('branding/application.ico'))
    assert image.ico.sizes()=={(size,size) for size in [16,24,32,48,64,128,256]}
    for size in [16,24,32,48,64,128,256]:
        frame=image.ico.getimage((size,size)).convert('RGBA')
        assert frame.getextrema()[3][0]==0 and frame.getextrema()[3][1]>200
        pixels=list(frame.getdata())
        assert any(r>b*1.3 and r>100 and a>100 for r,g,b,a in pixels)
        assert any(b>r*1.3 and b>100 and a>100 for r,g,b,a in pixels)


@pytest.fixture
def window(tmp_path):
    app=W.QApplication.instance() or W.QApplication([])
    store=Store(tmp_path/'contracts.sqlite3');store.set_setting('folder',str(tmp_path));store.db.close()
    window=Window(tmp_path)
    yield window,app
    window.close()


def test_shared_top_and_bottom_actions_and_page_enablement(window,monkeypatch):
    window,app=window
    assert isinstance(window.inbox,CrystalPanel)
    assert window.tabs.iconSize()==QtCore.QSize(24,24)
    assert window.main_toolbar.iconSize()==QtCore.QSize(32,32)
    assert not window.windowIcon().isNull()
    called=[]
    monkeypatch.setattr(window,'add_dialog',lambda:called.append('add'))
    top=window.main_toolbar.widgetForAction(window.actions['add'])
    bottom=next(b for b in window.findChildren(W.QPushButton) if b.property('actionKey')=='add')
    top.click();bottom.click();assert called==['add','add']
    window.tabs.setCurrentIndex(1)
    assert not window.actions['add'].isEnabled() and not bottom.isEnabled()
    assert not window.actions['pdf'].isEnabled() and not window.actions['save'].isEnabled()
    assert window.actions['settings'].isEnabled() and window.actions['help'].isEnabled()


def test_toolbar_save_and_pdf_open_follow_selection(window,tmp_path,monkeypatch):
    window,app=window
    scan=tmp_path/'scan.pdf';archive=tmp_path/'T123_Test_IX-3_20260201.pdf'
    make_pdf(scan,1);make_pdf(archive,1)
    monkeypatch.setattr(window,'start_next',lambda:None)
    window.add_files([str(scan)])
    window.load_fields(Contract('T123','Test','Test','IX-3','20260201'))
    window.set_queue_state(str(scan),'Felismerve')
    window.confirm.setChecked(True)
    called=[];monkeypatch.setattr(window,'save',lambda:called.append('save'))
    window.main_toolbar.widgetForAction(window.actions['save']).click();window.save_button.click()
    assert called==['save','save']
    urls=[];monkeypatch.setattr(QtGui.QDesktopServices,'openUrl',lambda url:urls.append(url.toLocalFile()) or True)
    window.actions['pdf'].trigger();assert Path(urls[-1])==scan
    window.tabs.setCurrentIndex(1)
    row=next(r for r in range(window.table.rowCount()) if window.table.item(r,0).text()==archive.name)
    window.table.selectRow(row);window.actions['pdf'].trigger()
    assert Path(urls[-1])==archive
    assert not window.actions['save'].isEnabled()
    assert window.contract_details['code'].text()=='T123'
    assert window.contract_details['date'].text()=='2026.02.01.'
    window.tabs.setCurrentIndex(0);window.clear_queue()
    assert not window.actions['save'].isEnabled() and not window.actions['pdf'].isEnabled()
    assert not window.save_button.isEnabled()

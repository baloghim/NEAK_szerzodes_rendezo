"""Capture the actual Qt application using an isolated synthetic QA workspace.

This is a documentation/test tool. Normal application startup never seeds data.
"""
import argparse
from pathlib import Path
import tempfile
import shutil
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from PyQt5 import QtCore, QtGui, QtWidgets as W
from app.gui import Window
from app.core import Store,Contract
from app.theme import icon,catalog,apply_theme,asset_path


def synthetic_pdf(path):
    image=Image.new('RGB',(1100,1500),'white');d=ImageDraw.Draw(image)
    fonts=['C:/Windows/Fonts/arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    font=next((ImageFont.truetype(p,21) for p in fonts if Path(p).exists()),ImageFont.load_default())
    bold=next((ImageFont.truetype(p,30) for p in fonts if Path(p).exists()),font)
    d.text((65,65),'SZINTETIKUS TESZTDOKUMENTUM',fill='#244b75',font=bold)
    d.text((65,125),'Otthonápolási szerződés – IX/3. melléklet',fill='black',font=font)
    d.multiline_text((65,175),'Szolgáltató NEAK kódja: T123\nSzolgáltató neve: Szintetikus Otthonápolás Kft.\nHatályos: 2026.02.01. napjától',fill='black',font=font,spacing=12)
    d.text((65,330),'Az ábra kizárólag a felület ellenőrzésére készült.',fill='#666666',font=font)
    left,top,width,rowheight=65,430,970,66
    for row in range(11):
        y=top+row*rowheight;d.line((left,y,left+width,y),fill='#667788',width=2)
        for col in range(5):d.line((left+col*width/4,y,left+col*width/4,y+rowheight),fill='#667788',width=2)
        if row<10:
            for col,value in enumerate(['Azonosító' if row==0 else f'TESZT-{row:03}',
                                        'Melléklet' if row==0 else 'IX-3',
                                        'Állapot' if row==0 else 'Szintetikus',
                                        'Kezdet' if row==0 else '2026.02.01.']):
                d.text((left+col*width/4+10,y+20),value,fill='black',font=font)
    image.save(path,'PDF')


def capture(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    app=W.QApplication.instance() or W.QApplication([])
    apply_theme(app)
    with tempfile.TemporaryDirectory(prefix='neak-ui-qa-') as tmp:
        root=Path(tmp); archive=root/'Szerződések';archive.mkdir()
        sample=root/'szintetikus-szkenneles.pdf';synthetic_pdf(sample)
        names=['T123_Szintetikus_IX-1_20240101.pdf','T123_Szintetikus_IX-2_20250201.pdf',
               'T123_Szintetikus_IX-3_20260201.pdf','T124_Minta_IX-1_20261101.pdf']
        for name in names:shutil.copyfile(sample,archive/name)
        settings=root/'beallitasok';settings.mkdir()
        store=Store(settings/'contracts.sqlite3');store.set_setting('folder',str(archive))
        store.provider('T123','Szintetikus Otthonápolás Kft.','Szintetikus')
        store.mark(archive/names[0],'Feltöltve');store.mark(archive/names[1],'Ellenőrizendő')
        store.mark(archive/names[2],'Nincs feltöltve');store.db.close()
        window=Window(settings)
        # Populate without running OCR; all fixtures are explicitly labelled QA.
        window.start_next=lambda:None
        for i in range(3):
            file=root/f'szkenneles_{i+1:03}.pdf';shutil.copyfile(sample,file);window.add_files([str(file)])
            data=Contract('T123','Szintetikus Otthonápolás Kft.','Szintetikus','IX-3','20260201')
            window.items[str(file)]['data']=data
            window.set_queue_state(str(file),'Felismerve' if i<2 else 'Feldolgozás')
        window.pending.clear();window.queue.setCurrentRow(2)
        window.load_fields(data)
        window.resize(1640,960);window.show();app.processEvents()
        window.grab().save(str(output/'actual-scan.png'))
        window.tabs.setCurrentIndex(1);app.processEvents()
        row=next(r for r in range(window.table.rowCount()) if window.table.item(r,1).text()=='T123' and window.table.item(r,3).text()=='IX-3')
        window.table.selectRow(row);app.processEvents()
        window.grab().save(str(output/'actual-browse.png'))
        # Genuine Qt widget catalog using the same icon loader as all actions.
        dialog=W.QDialog();dialog.setWindowTitle('Valódi ikonok és eredetük')
        grid=W.QGridLayout(dialog)
        selected=['add','remove','clear','retry','skip','save','browse','settings','help','refresh','filter','rotate_left','rotate_right','save_rotation','folder','pdf','processing','ready','warning','error']
        for i,key in enumerate(selected):
            row,column=divmod(i,4);entry=catalog()[key]
            cell=W.QWidget();layout=W.QVBoxLayout(cell)
            button=W.QToolButton();button.setIcon(icon(key));button.setIconSize(QtCore.QSize(48,48));button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon);button.setText(entry['label']);layout.addWidget(button)
            label=W.QLabel(entry['set']+'\n'+entry['original']);label.setWordWrap(True);label.setAlignment(QtCore.Qt.AlignCenter);layout.addWidget(label)
            grid.addWidget(cell,row,column)
        provenance=W.QLabel('Forrás: Everaldo Coelho / Crystal Clear – github.com/niko-yanev/crystal-clear (LGPL 2.1+)\nPDF: KDE Artists / Crystal SVG – github.com/Fat-Zer/tdelibs, pics/LICENSE.crystalsvg (LGPL 2.1 + artwork add-on)\nEredeti fájlnevek, pontos források és eltérések: docs/ICON_MAPPING.md; assets/icons/catalog.json')
        provenance.setWordWrap(True);grid.addWidget(provenance,5,0,1,4)
        dialog.resize(1400,1000);dialog.show();app.processEvents();dialog.grab().save(str(output/'icon-comparison.png'));dialog.close()
        window.close()
    return app


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='docs');args=parser.parse_args()
    capture(args.output)

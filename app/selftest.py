"""Synthetic smoke check for the installed package; no private input is used."""
import os
import time
from pathlib import Path
import tempfile
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtWidgets import QApplication
from .gui import Window
from .documents import recognize
from .core import extract_contract, save_copy


def run():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='neak-smoke-') as directory:
        root = Path(directory)
        image = Image.new('RGB', (1700, 2200), 'white')
        draw = ImageDraw.Draw(image)
        candidates = ['C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
        font = next((ImageFont.truetype(p, 42) for p in candidates if Path(p).exists()), ImageFont.load_default())
        draw.multiline_text((100, 300), 'Szolgáltató NEAK kódja: 4321\nSzolgáltató neve: Minta Kft.\nIX/2. számú melléklet\nHatályos: 2026.02.01. napjától', fill='black', font=font, spacing=35)
        source = root/'input.pdf'
        image.save(source, 'PDF')
        data = extract_contract(recognize(source), {'4321':'Minta'})
        assert data.filename() == '4321_Minta_IX-2_20260201.pdf', repr(data)
        window = Window(root/'settings')
        window.folder.setText(str(root))
        window.store.provider('4321', 'Minta Kft.', 'Minta')
        window.add_files([str(source)])
        deadline = time.monotonic() + 120
        while window.items[str(source)]['state'] == 'Várakozik' and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.02)
        assert window.items[str(source)]['state'] == 'Felismerve'
        assert window.filename.text() == '4321_Minta_IX-2_20260201.pdf'
        window.scan_preview.open(source)
        assert window.scan_preview.document is not None
        destination = root/data.filename()
        window.confirm.setChecked(True)
        window.next_check.setChecked(False)
        window.save()
        assert destination.exists()
        assert window.items[str(source)]['state'] == 'Kész'
        window.store.mark(destination, 'Feltöltve')
        window.refresh()
        assert window.table.rowCount() == 2
        window.table.selectRow(0)
        app.processEvents()
        window.close()
        print('PASS: bundled OCR hun+eng, extraction, Qt, PDF preview, copy, SQLite, browse')
    return 0

"""Synthetic smoke check for the installed package; no private input is used."""
import os
import time
from pathlib import Path
import tempfile
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtWidgets import QApplication
from .gui import Window
from .documents import recognize
from .core import extract_contract, Store


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
        settings = root/'settings'
        settings.mkdir()
        store = Store(settings/'contracts.sqlite3')
        store.set_setting('folder', str(root))
        store.db.close()
        window = Window(settings)
        if os.name == 'nt':
            assert window.native_drops is not None, window.native_drop_error
        def fail(message):
            raise RuntimeError(str(message))
        window.error = fail
        window.folder.setText(str(root))
        window.store.provider('4321', 'Minta Kft.', 'Minta')
        window.add_files([str(source)])
        deadline = time.monotonic() + 120
        while (window.items[str(source)]['state'] == 'Várakozik' or any(job.isRunning() for job in window.jobs)) and time.monotonic() < deadline:
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
        if os.name == 'nt':
            from .ole_smoke import run_native_cases
            assert window.native_drops is not None, 'Native HWND drop targets not registered'
            assert len(window.native_drops.handles) == 2
            previous = window.queue.count()
            extra = run_native_cases(window.staging.name, source.read_bytes(), window.native_drops.targets[0])
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                app.processEvents()
                if (window.queue.count() == previous + len(extra) and not window.pending
                        and not any(job.isRunning() for job in window.jobs)
                        and all(item['state'] != 'Várakozik' for item in window.items.values())):
                    break
                time.sleep(.02)
            assert window.queue.count() == previous + len(extra), 'OLE files not appended'
            assert all(item['data'].code == '4321' for item in window.items.values())
            assert all(item['state'] in ('Felismerve', 'Kész') for item in window.items.values())
            print('PASS: packaged native OLE transfers append to existing queue and run OCR')
        window.close()
        print('PASS: bundled OCR hun+eng, extraction, Qt, PDF preview, copy, SQLite, browse')
    return 0

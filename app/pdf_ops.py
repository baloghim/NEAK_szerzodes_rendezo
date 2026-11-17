"""Lossless page-rotation metadata and failure-safe PDF replacement."""
from pathlib import Path
import os
import tempfile
import threading
import pypdfium2 as pdfium
from .core import digest

# PDFium is not thread-safe, even for separate documents. OCR subprocesses run
# outside this lock; only native PDF access/render/save is serialized.
PDF_LOCK = threading.RLock()


def write_rotated(source, destination, rotations):
    with PDF_LOCK:
        document = pdfium.PdfDocument(Path(source).read_bytes())
        try:
            for index, angle in rotations.items():
                if int(index) < 0 or int(index) >= len(document) or angle % 90:
                    raise ValueError('Érvénytelen oldalforgatás.')
                page = document[int(index)]
                try:
                    page.set_rotation((page.get_rotation() + angle) % 360)
                finally:
                    page.close()
            document.save(str(destination))
            expected = len(document)
        finally:
            document.close()
        check = pdfium.PdfDocument(Path(destination).read_bytes())
        try:
            if len(check) != expected:
                raise OSError('A PDF-másolat ellenőrzése sikertelen.')
        finally:
            check.close()
    with open(destination, 'rb+') as stream:
        os.fsync(stream.fileno())


def replace_rotated(path, rotations, expected_hash=None):
    """Stage in the SAME directory, validate, then one atomic replacement.

    The caller must obtain explicit overwrite confirmation. On any failure
    before os.replace the source is byte-for-byte untouched.
    """
    path = Path(path)
    before = digest(path)
    if expected_hash and before != expected_hash:
        raise OSError('A dokumentum időközben megváltozott. Nyisd meg újra.')
    handle, name = tempfile.mkstemp(prefix='.neak-rotation-', suffix='.tmp', dir=path.parent)
    os.close(handle)
    temporary = Path(name)
    try:
        write_rotated(path, temporary, rotations)
        if digest(path) != before:
            raise OSError('A dokumentum időközben megváltozott; a mentés megszakadt.')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

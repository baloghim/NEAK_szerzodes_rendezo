"""Local document handling. No document data leaves the machine."""
from pathlib import Path
from email import policy
from email.parser import BytesParser
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from .core import extract_contract
from .pdf_ops import PDF_LOCK
import pypdfium2 as pdfium


def resource_dir():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def tesseract_command():
    bundled = resource_dir() / 'ocr' / 'tesseract.exe'
    if getattr(sys, 'frozen', False) and not bundled.exists():
        raise RuntimeError('Hiányos kiadási csomag: az OCR futtatható állomány nem található.')
    return str(bundled) if bundled.exists() else 'tesseract'


@dataclass
class Recognition:
    text: str
    rotations: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def run_ocr(image, psm=3):
    with tempfile.TemporaryDirectory(prefix='neak-ocr-') as folder:
        imagepath = Path(folder) / 'page.png'
        image.save(imagepath)
        command = [tesseract_command(), str(imagepath), 'stdout', '-l', 'hun+eng', '--psm', str(psm)]
        if (resource_dir() / 'ocr' / 'tessdata').exists():
            command += ['--tessdata-dir', str(resource_dir() / 'ocr' / 'tessdata')]
        completed = subprocess.run(command, capture_output=True, timeout=180,
                                   creationflags=0x08000000 if os.name == 'nt' else 0)
        if completed.returncode:
            raise RuntimeError('OCR-hiba: ' + completed.stderr.decode('utf-8', errors='replace')[-1500:])
        return completed.stdout.decode('utf-8', errors='replace')


def field_score(text):
    data = extract_contract(text)
    return sum(bool(getattr(data, key)) for key in ('code', 'provider', 'annex', 'date'))


def orient_image(image, automatic=True):
    extrema = image.convert('L').getextrema()
    if extrema[0] == extrema[1] and extrema[0] >= 250:
        return '', 0, ''
    # Fast path: an upright page with all four labelled fields needs one OCR.
    candidates = []
    for angle in ((0, 90, 270, 180) if automatic else (0,)):
        oriented = image if angle == 0 else image.rotate(-angle, expand=True)
        # PSM 3 can internally read vertical text without reporting rotation.
        # PSM 6 keeps the tested angle meaningful; use layout mode 3 only later.
        text = run_ocr(oriented, psm=6)
        score = field_score(text)
        candidates.append((score, angle, text))
        if score == 4:
            break
    # Field count, not random OCR character count, determines orientation.
    best = max(candidates, key=lambda item: item[0])
    # Tables can need a different segmentation, only retry a weak best candidate.
    if best[0] < 4:
        oriented = image if best[1] == 0 else image.rotate(-best[1], expand=True)
        alternative = run_ocr(oriented, psm=3)
        if field_score(alternative) > best[0]:
            best = (field_score(alternative), best[1], alternative)
    warning = ''
    if automatic and best[0] == 0:
        # No readable fields: do not arbitrarily rotate covers/stamps.
        best = candidates[0]
    elif automatic and best[1] and sum(item[0] == best[0] for item in candidates) > 1:
        warning = 'Az oldal tájolása nem egyértelmű; ellenőrizd a betekintőben.'
    return best[2], best[1], warning


def recognize(path, auto_orient=True, detailed=False, initial_rotations=None):
    result = Recognition('')
    initial_rotations = initial_rotations or {}
    pages = []
    with PDF_LOCK:
        document = pdfium.PdfDocument(Path(path).read_bytes())
        count = len(document)
    try:
        for index in range(count):
            embedded = ''
            try:
                with PDF_LOCK:
                    page = document[index]
                    try:
                        textpage = page.get_textpage()
                        try:
                            embedded = textpage.get_text_range()
                        finally:
                            textpage.close()
                        initial = initial_rotations.get(index, 0)
                        if field_score(embedded) == 4 and not auto_orient:
                            image = None
                        else:
                            bitmap = page.render(scale=2.5,rotation=initial)
                            try:
                                image = bitmap.to_pil().copy()
                            finally:
                                bitmap.close()
                    finally:
                        page.close()
                if image is None:
                    text, angle, warning = embedded, 0, ''
                else:
                    text, angle, warning = orient_image(image, auto_orient)
                    # Preserve useful embedded values if OCR has fewer fields.
                    if field_score(embedded) > field_score(text):
                        text = embedded
                pages.append(text)
                result.rotations[index] = (initial + angle) % 360
                if warning:
                    result.warnings.append(f'{index+1}. oldal: {warning}')
            except Exception as error:
                # Other pages and their valid fields remain available for correction.
                pages.append(embedded)
                result.warnings.append(f'{index+1}. oldal feldolgozási hibája: {error}')
    finally:
        with PDF_LOCK:
            document.close()
    result.text = '\n'.join(pages)
    return result if detailed else result.text


def import_files(paths, staging):
    """Extract only PDFs; generate local names instead of trusting attachment paths."""
    staging = Path(staging)
    result = []
    for raw in paths:
        path = Path(raw)
        suffix = path.suffix.lower()
        if suffix == '.pdf':
            result.append(path)
            continue
        attachments = []
        if suffix == '.eml':
            message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
            attachments = [(part.get_filename() or '', part.get_payload(decode=True))
                           for part in message.walk() if not part.is_multipart()]
        elif suffix == '.msg':
            import extract_msg
            with extract_msg.Message(str(path)) as message:
                attachments = [(a.longFilename or a.shortFilename or '', a.data) for a in message.attachments]
        else:
            raise ValueError('Csak PDF, MSG vagy EML importálható.')
        for name, data in attachments:
            if name.lower().endswith('.pdf') and isinstance(data, bytes):
                if not data.startswith(b'%PDF-'):
                    raise ValueError('A melléklet nem érvényes PDF.')
                handle, filename = tempfile.mkstemp(suffix='.pdf', prefix='melleklet-', dir=staging)
                with os.fdopen(handle, 'wb') as stream:
                    stream.write(data)
                result.append(Path(filename))
    return result

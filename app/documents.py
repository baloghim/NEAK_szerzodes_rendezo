"""Local document handling. No document data leaves the machine."""
from pathlib import Path
from email import policy
from email.parser import BytesParser
import os
import subprocess
import sys
import tempfile
import pypdfium2 as pdfium


def resource_dir():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def tesseract_command():
    bundled = resource_dir() / 'ocr' / 'tesseract.exe'
    if getattr(sys, 'frozen', False) and not bundled.exists():
        raise RuntimeError('Hiányos kiadási csomag: az OCR futtatható állomány nem található.')
    return str(bundled) if bundled.exists() else 'tesseract'


def recognize(path):
    pages = []
    document = pdfium.PdfDocument(str(path))
    try:
        for page in document:
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            textpage.close()
            # OCR every page lacking usable text, including stamp-only cover pages.
            if len(text.strip()) < 80 or 'hatály' not in text.lower():
                image = page.render(scale=3).to_pil()
                with tempfile.TemporaryDirectory(prefix='neak-ocr-') as folder:
                    imagepath = Path(folder) / 'page.png'
                    image.save(imagepath)
                    command = [tesseract_command(), str(imagepath), 'stdout', '-l', 'hun+eng', '--psm', '3']
                    if (resource_dir() / 'ocr' / 'tessdata').exists():
                        command += ['--tessdata-dir', str(resource_dir() / 'ocr' / 'tessdata')]
                    completed = subprocess.run(command, capture_output=True, timeout=180,
                                               creationflags=0x08000000 if os.name == 'nt' else 0)
                    if completed.returncode:
                        raise RuntimeError('OCR-hiba: ' + completed.stderr.decode('utf-8', errors='replace')[-1500:])
                    text += '\n' + completed.stdout.decode('utf-8', errors='replace')
            pages.append(text)
            page.close()
    finally:
        document.close()
    return '\n'.join(pages)


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

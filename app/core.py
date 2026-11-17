from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import hashlib
import os
import re
import shutil
import sqlite3
import unicodedata

STATUSES = ('Ismeretlen', 'Nincs feltöltve', 'Feltöltve', 'Ellenőrizendő')


def clean_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', value.strip())
    return re.sub(r'\s+', '_', value).strip(' ._')


def parse_date(value):
    digits = re.sub(r'\D', '', value)
    if len(digits) != 8:
        raise ValueError('A dátum formátuma ÉÉÉÉ.HH.NN.')
    return datetime.strptime(digits, '%Y%m%d').strftime('%Y%m%d')


@dataclass
class Contract:
    code: str = ''
    provider: str = ''
    short: str = ''
    annex: str = ''
    date: str = ''
    warnings: list = field(default_factory=list)

    def validate(self):
        if not re.fullmatch(r'[A-Z0-9]{4}', self.code):
            raise ValueError('A NEAK-kód négy betű vagy szám legyen.')
        if not self.provider.strip() or not clean_name(self.short):
            raise ValueError('A szolgáltató és a rövid név kötelező.')
        if self.annex not in ('IX-1', 'IX-2', 'IX-3'):
            raise ValueError('Válassz IX-1, IX-2 vagy IX-3 mellékletet.')
        parse_date(self.date)

    def filename(self):
        self.validate()
        return f'{self.code}_{clean_name(self.short)}_{self.annex}_{parse_date(self.date)}.pdf'


def parse_filename(filename):
    match = re.fullmatch(r'([A-Za-z0-9]{4})_(.+)_IX[-_/]([123])_(\d{4}[-.]?\d{2}[-.]?\d{2})\.pdf', filename, re.I)
    if not match:
        raise ValueError('Nem értelmezhető szerződésfájlnév.')
    code, short, annex, date = match.groups()
    return Contract(code.upper(), short.replace('_', ' '), short, 'IX-' + annex, parse_date(date))


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').lower()


def extract_contract(text, providers=None):
    """Labelled values across lines/tables; unrelated signature dates never qualify."""
    text = unicodedata.normalize('NFC', text.replace('\r', ''))
    plain = fold(text)
    candidates = {key: [] for key in ('code', 'provider', 'annex', 'date')}
    code_label = r'(?:szolgaltato\s+)?neak\s*[- ]?\s*kod(?:ja)?'
    date_label = r'hatalyos(?:sag(?:\s+kezdete)?)?'
    candidates['code'] += re.findall(code_label + r'\s*[:：|]?\s*([a-z0-9]{4})\b', plain)
    candidates['annex'] += re.findall(r'\b(?:ix|1x|lx)\s*[/.-]\s*(iii|ii|[123il])\s*\.?\b', plain)
    candidates['date'] += re.findall(date_label + r'\s*[:：|]?\s*(\d{4}\s*[.\-/]\s*\d{1,2}\s*[.\-/]\s*\d{1,2})', plain)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    labels = r'(?:szolgaltato\s+neve|'+code_label+'|'+date_label+r'|szekhely|adoszam|mukodesi)'
    for index, line in enumerate(lines):
        normalized = fold(line)
        match = re.search(r'szolgaltato\s+neve\s*[:：|]?\s*', normalized)
        if match:
            value = line[match.end():].strip(' :：|\t')
            if not value and index+1 < len(lines):
                value = lines[index+1].strip(' :：|\t')
            # A following table header is not the provider's name.
            if value and not re.match(labels, fold(value)):
                value = re.split(r'\s*[|\t]\s*', value)[0].strip()
                stop = re.search(r'\s+(?:'+labels+r')\s*:', fold(value))
                candidates['provider'].append(value[:stop.start()].strip() if stop else value)
        # Explicit table columns: labels in one row, values in the next.
        cells = [part.strip() for part in re.split(r'[|\t]| {3,}', line) if part.strip()]
        if len(cells) > 1 and index+1 < len(lines):
            values = [part.strip() for part in re.split(r'[|\t]| {3,}', lines[index+1]) if part.strip()]
            header_count = sum(bool(re.fullmatch('(?:'+code_label+'|szolgaltato\\s+neve|'+date_label+')\\s*:?',fold(cell))) for cell in cells)
            if len(cells) == len(values) and header_count >= 2:
                for label, value in zip(cells, values):
                    label = fold(label)
                    key = ('code' if re.fullmatch(code_label+r'\s*:?',label) else
                           'provider' if re.fullmatch(r'szolgaltato\s+neve\s*:?',label) else
                           'date' if re.fullmatch(date_label+r'\s*:?',label) else None)
                    if key:
                        candidates[key].append(value)
    result = Contract()
    for key, values in candidates.items():
        normalized = {}
        for value in values:
            if key == 'code':
                value = value.upper().strip()
                if not re.fullmatch(r'[A-Z0-9]{4}', value):
                    continue
            elif key == 'annex':
                value = 'IX-' + {'i':'1','l':'1','ii':'2','iii':'3'}.get(value, value)
            elif key == 'date':
                parts = re.findall(r'\d+', value)
                try:
                    if len(parts) != 3:
                        raise ValueError()
                    value = datetime(*map(int, parts)).strftime('%Y%m%d')
                except ValueError:
                    result.warnings.append('Érvénytelen hatályossági dátum.')
                    continue
            else:
                value = re.sub(r'\s+', ' ', value).strip()
                if not value:
                    continue
            normalized[value.casefold()] = value
        if len(normalized) == 1:
            setattr(result, key, next(iter(normalized.values())))
        else:
            result.warnings.append(f'Hiányzó vagy ellentmondó adat: {key}.')
    known = (providers or {}).get(result.code)
    result.short = known if known else re.sub(r'\s+(?:Bt|Kft|Zrt)\.?$', '', result.provider, flags=re.I)
    if not known:
        result.warnings.append('A szolgáltató rövid nevét ellenőrizni kell.')
    return result


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path))
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS providers (code TEXT PRIMARY KEY, name TEXT, short TEXT);
        CREATE TABLE IF NOT EXISTS documents (
          path TEXT PRIMARY KEY, hash TEXT, status TEXT NOT NULL, uploaded_at TEXT);
        ''')
        self.db.commit()

    def setting(self, key, default=''):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, str(value)))
        self.db.commit()

    def providers(self):
        return dict(self.db.execute('SELECT code, short FROM providers'))

    def provider(self, code, name, short):
        self.db.execute('INSERT OR REPLACE INTO providers VALUES (?,?,?)', (code, name, short))
        self.db.commit()

    def status(self, path):
        row = self.db.execute('SELECT status, uploaded_at FROM documents WHERE path=?', (str(Path(path).absolute()),)).fetchone()
        return row if row else ('Ismeretlen', None)

    def mark(self, path, status, sha=None):
        if status not in STATUSES:
            raise ValueError('Ismeretlen állapot')
        path = str(Path(path).absolute())
        old = self.db.execute('SELECT hash FROM documents WHERE path=?', (path,)).fetchone()
        timestamp = datetime.now().astimezone().isoformat(timespec='seconds') if status == 'Feltöltve' else None
        self.db.execute('INSERT OR REPLACE INTO documents VALUES (?,?,?,?)', (path, sha or (old[0] if old else None), status, timestamp))
        self.db.commit()

    def duplicate(self, sha):
        return self.db.execute('SELECT path FROM documents WHERE hash=? LIMIT 1', (sha,)).fetchone()


def save_copy(source, destination, store, allow_duplicate=False):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('A forrás és a cél nem lehet azonos.')
    sha = digest(source)
    if store.duplicate(sha) and not allow_duplicate:
        raise ValueError('Azonos tartalmú dokumentum már szerepel a nyilvántartásban.')
    # Exclusive creation protects against concurrent writers, including UNC shares.
    created = False
    try:
        with open(destination, 'xb') as target:
            created = True
            with open(source, 'rb') as original:
                shutil.copyfileobj(original, target)
            target.flush()
            os.fsync(target.fileno())
        if digest(destination) != sha:
            raise OSError('A másolat ellenőrzése sikertelen.')
        store.mark(destination, 'Nincs feltöltve', sha)
    except Exception:
        if created:
            try:
                destination.unlink()
            except OSError:
                pass
        raise
    return destination

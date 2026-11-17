from pathlib import Path
import pytest
from app.core import Contract, Store, extract_contract, parse_date, parse_filename, save_copy

@pytest.mark.parametrize('code,short,annex,expected', [
 ('B321','NED-HOME-CARE','IX-1','B321_NED-HOME-CARE_IX-1_20260201.pdf'),
 ('A576','GRANGENIUS','IX-1','A576_GRANGENIUS_IX-1_20260201.pdf'),
 ('A128','Kisbéri_Önkéntes','IX-2','A128_Kisbéri_Önkéntes_IX-2_20260201.pdf')])
def test_names(code, short, annex, expected):
    # Synthetic metadata only: no real document text is included.
    assert Contract(code, 'Teszt szolgáltató', short, annex, '2026.02.01.').filename() == expected
    assert parse_filename(expected).filename() == expected

@pytest.mark.parametrize('date', ['20260230','20251301','2026','20250229'])
def test_invalid_date(date):
    with pytest.raises(ValueError): parse_date(date)


def test_labels_and_cover_page():
    text = 'Érkezett: 2026.03.15.\nKelt: 2026.01.12.\n\f\nSzolgáltató NEAK kódja: T123\nSzolgáltató neve: Minta Kft.\nIX/2. számú melléklet\nHatályos: 2026.02.01. napjától'
    data = extract_contract(text, {'T123':'Minta'})
    assert data.filename() == 'T123_Minta_IX-2_20260201.pdf'
    assert not data.warnings


def test_conflicting_fields():
    data = extract_contract('NEAK kód: T123\nNEAK kód: T124\nHatályos: 2026.01.01.\nHatályos: 2026.02.01.\nIX/1.\nIX/2.')
    assert not data.code and not data.date and not data.annex
    assert data.warnings


def test_unlabelled_date_is_not_effective():
    assert extract_contract('Kelt: 2026.02.01.\nÉrkezett 2026.03.01.').date == ''


def test_exclusive_copy_and_persistence(tmp_path):
    source = tmp_path/'source.pdf'
    source.write_bytes(b'%PDF-synthetic')
    db = tmp_path/'index.sqlite3'
    store = Store(db)
    destination = tmp_path/'copy.pdf'
    save_copy(source, destination, store)
    assert source.read_bytes() == destination.read_bytes()
    assert store.status(destination)[0] == 'Nincs feltöltve'
    with pytest.raises(FileExistsError): save_copy(source, destination, store, True)
    with pytest.raises(ValueError, match='Azonos tartalmú'): save_copy(source, tmp_path/'duplicate.pdf', store)
    store.mark(destination, 'Feltöltve')
    store.db.close()
    reopened = Store(db)
    assert reopened.status(destination)[0] == 'Feltöltve'
    assert reopened.status(destination)[1]


def test_network_failure_does_not_register(tmp_path):
    source = tmp_path/'source.pdf'
    source.write_bytes(b'%PDF-synthetic')
    store = Store(tmp_path/'index.sqlite3')
    target = tmp_path/'unavailable'/'copy.pdf'
    with pytest.raises(OSError): save_copy(source,target,store)
    assert store.status(target)[0] == 'Ismeretlen'
    assert source.exists()


def test_nonconforming_legacy_filename():
    assert parse_filename('T123_Minta_Szolgáltató_IX-3_2025-06-01.pdf').date == '20250601'
    with pytest.raises(ValueError): parse_filename('../bad.pdf')


def test_partial_copy_cleanup(tmp_path, monkeypatch):
    import app.core as core
    source = tmp_path/'original.pdf'
    source.write_bytes(b'%PDF-synthetic')
    target = tmp_path/'copy.pdf'
    store = Store(tmp_path/'index.sqlite3')
    def interrupted(original, destination):
        destination.write(b'partial')
        raise OSError('Network disconnected')
    monkeypatch.setattr(core.shutil,'copyfileobj',interrupted)
    with pytest.raises(OSError): save_copy(source,target,store)
    assert not target.exists()
    assert source.read_bytes() == b'%PDF-synthetic'
    assert store.status(target)[0] == 'Ismeretlen'

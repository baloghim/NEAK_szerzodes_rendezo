from pathlib import Path
import ctypes
import hashlib
import pytest
from PIL import Image, ImageDraw
import pypdfium2 as pdfium
from app.pdf_ops import write_rotated, replace_rotated
from app.core import extract_contract
from app.documents import orient_image


def make_pdf(path, count=2):
    images=[]
    for index in range(count):
        image=Image.new('RGB',(300+index*20,450),'white')
        ImageDraw.Draw(image).text((20,30),f'Synthetic page {index+1}',fill='black')
        images.append(image)
    images[0].save(path,'PDF',save_all=True,append_images=images[1:])


def image_streams(path):
    doc=pdfium.PdfDocument(path.read_bytes())
    result=[]
    try:
        for page in doc:
            try:
                result.append([bytes(obj.get_data()) for obj in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE])])
            finally: page.close()
    finally: doc.close()
    return result


def rotations(path):
    doc=pdfium.PdfDocument(path.read_bytes())
    result=[]
    try:
        for page in doc:
            result.append(page.get_rotation());page.close()
    finally:doc.close()
    return result


def test_lossless_per_page_metadata_rotation(tmp_path):
    source=tmp_path/'source.pdf';target=tmp_path/'target.pdf'
    make_pdf(source)
    original=source.read_bytes()
    write_rotated(source,target,{0:90,1:270})
    assert rotations(target)==[90,270]
    assert source.read_bytes()==original
    assert image_streams(target)==image_streams(source)
    replace_rotated(target,{0:90})
    assert rotations(target)==[180,270]
    assert image_streams(target)==image_streams(source)


def test_failed_replace_keeps_original(tmp_path,monkeypatch):
    import app.pdf_ops as ops
    source=tmp_path/'source.pdf';make_pdf(source)
    original=source.read_bytes()
    def fail(*args):raise OSError('synthetic disconnected network')
    monkeypatch.setattr(ops.os,'replace',fail)
    with pytest.raises(OSError):replace_rotated(source,{0:90})
    assert source.read_bytes()==original
    assert list(tmp_path.iterdir())==[source]


def test_serialization_failure_keeps_original(tmp_path,monkeypatch):
    import app.pdf_ops as ops
    source=tmp_path/'source.pdf';make_pdf(source)
    original=source.read_bytes()
    def fail(src,target,rotations):
        Path(target).write_bytes(b'partial')
        raise OSError('synthetic disk full')
    monkeypatch.setattr(ops,'write_rotated',fail)
    with pytest.raises(OSError):replace_rotated(source,{0:90})
    assert source.read_bytes()==original
    assert list(tmp_path.iterdir())==[source]


def test_concurrent_external_change_not_overwritten(tmp_path):
    source=tmp_path/'source.pdf';make_pdf(source)
    with pytest.raises(OSError,match='megváltozott'):
        replace_rotated(source,{0:90},'outdated-hash')
    assert rotations(source)==[0,0]


@pytest.mark.parametrize('annex',['1','2','3'])
def test_split_fields_and_roman_annex(annex):
    text=f'Szolgáltató NEAK-kódja:\nT123\nSzolgáltató neve:\nSzintetikus Kft.\nIX / {annex}. számú melléklet\nHatályosság\nkezdete:\n2026.02.01.\nKelt: 2025.12.24.'
    data=extract_contract(text,{'T123':'Szintetikus'})
    assert (data.code,data.provider,data.annex,data.date)==('T123','Szintetikus Kft.','IX-'+annex,'20260201')


def test_table_columns_and_partial_fields():
    text='NEAK-kód | Szolgáltató neve | Hatályos\nT123 | Szintetikus Kft. | 2026.02.01.\nIX/3.'
    data=extract_contract(text)
    assert (data.code,data.provider,data.date,data.annex)==('T123','Szintetikus Kft.','20260201','IX-3')
    partial=extract_contract('NEAK-kód: T123\nIX/3.')
    assert partial.code=='T123' and partial.annex=='IX-3' and partial.date==''


def test_orientation_fast_path_not_four_runs(monkeypatch):
    import app.documents as docs
    calls=[]
    text='NEAK-kód: T123\nSzolgáltató neve: Szintetikus\nIX/3.\nHatályos: 2026.02.01.'
    def ocr(image,psm=3):calls.append(psm);return text
    monkeypatch.setattr(docs,'run_ocr',ocr)
    assert orient_image(Image.new('RGB',(100,200)))[1]==0
    assert calls==[6]


def test_orientation_uses_fields_instead_of_length(monkeypatch):
    import app.documents as docs
    good='NEAK-kód: T123\nSzolgáltató neve: Szintetikus\nIX/3.\nHatályos: 2026.02.01.'
    image=Image.new('RGB',(100,200),'white');image.putpixel((0,0),(0,0,0))
    calls=[]
    def ocr(candidate,psm=3):
        calls.append(candidate.size)
        return good if candidate.size==(200,100) else 'meaningless '*1000
    monkeypatch.setattr(docs,'run_ocr',ocr)
    text,angle,_=orient_image(image)
    assert angle==90 and text==good and len(calls)==2


def test_vertical_table_key_value_rows():
    data=extract_contract('Szolgáltató neve | Szintetikus Kft.\nNEAK-kód | T123\nHatályos | 2026.02.01.\nIX/3.')
    assert data.provider=='Szintetikus Kft.' and data.code=='T123' and data.date=='20260201'


def test_other_pages_survive_a_single_page_ocr_error(tmp_path,monkeypatch):
    import app.documents as docs
    source=tmp_path/'source.pdf';make_pdf(source)
    calls=[]
    text='NEAK-kód: T123\nSzolgáltató neve: Szintetikus\nIX/3.\nHatályos: 2026.02.01.'
    def recognize_page(image,automatic):
        calls.append(1)
        if len(calls)==2:raise OSError('synthetic page failure')
        return text,0,''
    monkeypatch.setattr(docs,'orient_image',recognize_page)
    result=docs.recognize(source,detailed=True)
    assert extract_contract(result.text).code=='T123'
    assert result.warnings and '2. oldal' in result.warnings[0]

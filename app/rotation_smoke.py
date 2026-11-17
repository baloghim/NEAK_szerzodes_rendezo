"""Synthetic rotated IX/3 acceptance test, including the packaged Windows EXE."""
from pathlib import Path
from PIL import Image, ImageDraw
from .documents import recognize
from .core import extract_contract
from .pdf_ops import write_rotated, PDF_LOCK
import pypdfium2 as pdfium


def run(root, font):
    image=Image.new('RGB',(1700,2200),'white')
    draw=ImageDraw.Draw(image)
    draw.multiline_text((100,300),
        'Szolgáltató NEAK kódja: 4321\nSzolgáltató neve: Minta Kft.\nIX/3. számú melléklet\nHatályos: 2026.02.01. napjától',
        fill='black',font=font,spacing=35)
    pages=[Image.new('RGB',image.size,'white')]
    pages += [image.rotate(-angle,expand=True) for angle in (0,90,180,270)]
    source=Path(root)/'rotated-input.pdf'
    pages[0].save(source,'PDF',save_all=True,append_images=pages[1:])
    original=source.read_bytes()
    result=recognize(source,detailed=True)
    assert not result.warnings,result.warnings
    assert result.rotations=={0:0,1:0,2:270,3:180,4:90},result.rotations
    data=extract_contract(result.text,{'4321':'Minta'})
    assert data.filename()=='4321_Minta_IX-3_20260201.pdf',repr(data)
    target=Path(root)/'rotated-output.pdf'
    write_rotated(source,target,result.rotations)
    assert source.read_bytes()==original
    with PDF_LOCK:
        document=pdfium.PdfDocument(target.read_bytes())
        try:
            assert len(document)==5
            for index in range(len(document)):
                page=document[index]
                assert page.get_rotation()==result.rotations[index]
                page.close()
        finally:document.close()
    print('PASS: real OCR IX/3, later pages, 0/90/180/270 orientations and lossless metadata output')
    return source,target,result

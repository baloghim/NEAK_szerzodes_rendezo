from email.message import EmailMessage
from pathlib import Path
from app.documents import import_files


def test_eml_pdf_only_and_safe_attachment_names(tmp_path):
    message = EmailMessage()
    message.set_content('Synthetic email')
    message.add_attachment(b'%PDF-synthetic', maintype='application', subtype='pdf', filename='../../outside.pdf')
    message.add_attachment(b'skip', maintype='application', subtype='octet-stream', filename='skip.exe')
    source = tmp_path/'mail.eml'
    source.write_bytes(message.as_bytes())
    staging = tmp_path/'staging'
    staging.mkdir()
    result = import_files([source], staging)
    assert len(result) == 1
    assert result[0].parent == staging
    assert result[0].read_bytes() == b'%PDF-synthetic'
    assert source.exists()


def test_multiple_pdfs_are_preserved(tmp_path):
    paths = [tmp_path/'a.pdf',tmp_path/'b.pdf']
    for path in paths: path.write_bytes(b'%PDF-synthetic')
    assert import_files(paths,tmp_path) == paths

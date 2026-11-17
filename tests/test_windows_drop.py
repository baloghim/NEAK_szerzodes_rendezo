import struct
import pytest
from app.windows_drop import Descriptor, descriptors, DropTarget, DWORD, POINTL, COPY
import ctypes as C


def group(names, wide=True):
    size = 592 if wide else 332
    result = bytearray(struct.pack('<I',len(names)))
    for name in names:
        entry = bytearray(size)
        encoded = name.encode('utf-16-le' if wide else 'cp1252')
        entry[72:72+len(encoded)] = encoded
        result.extend(entry)
    return bytes(result)


def test_multiple_unicode_descriptors():
    assert descriptors(group(['árvíztűrő.pdf','üzenet.msg'])) == [Descriptor('árvíztűrő.pdf'),Descriptor('üzenet.msg')]


def test_ansi_descriptor_and_size():
    data = bytearray(group(['mail.msg'],False))
    struct.pack_into('<I',data,4,0x40)
    struct.pack_into('<II',data,68,1,23)
    assert descriptors(data,False) == [Descriptor('mail.msg',2**32+23)]


@pytest.mark.parametrize('data',[b'',struct.pack('<I',2)+b'\0'*592,struct.pack('<I',1025)])
def test_truncated_or_excessive_list(data):
    with pytest.raises(ValueError): descriptors(data)


def test_copy_only_and_callbacks_do_not_raise():
    class Receiver:
        def accepts(self,data): return True
        def files(self,data): return ['synthetic.pdf'],[]
    deliveries=[]
    target=DropTarget(Receiver(),lambda paths,errors: deliveries.append((paths,errors)))
    effect=DWORD(3)
    target.enter(None,None,0,POINTL(),C.pointer(effect))
    assert effect.value == COPY
    target.drop(None,None,0,POINTL(),C.pointer(effect))
    assert deliveries == [(['synthetic.pdf'],[])]
    assert effect.value == COPY
    effect.value=2  # A source offering only MOVE must never be accepted.
    target.drop(None,None,0,POINTL(),C.pointer(effect))
    assert effect.value == 0 and len(deliveries)==1


def test_drop_failure_has_no_move_effect():
    class Receiver:
        def files(self,data): raise OSError('synthetic transfer failure')
    errors=[]
    target=DropTarget(Receiver(),lambda paths,err: errors.extend(err))
    effect=DWORD(3)
    assert target.drop(None,None,0,POINTL(),C.pointer(effect)) == 0
    assert effect.value==0 and errors


def test_native_windows_media_and_msg_import(tmp_path):
    import os
    if os.name != 'nt':
        pytest.skip('Real Windows COM/OLE APIs are required')
    from app.ole_smoke import run_native_cases
    assert len(run_native_cases(tmp_path,b'%PDF-synthetic acceptance fixture')) == 10


def test_fallback_qt_drop_always_copies():
    from PyQt5 import QtCore
    from app.gui import Window
    class Mime:
        def hasUrls(self): return True
        def urls(self): return [QtCore.QUrl.fromLocalFile('/synthetic.pdf')]
    class Event:
        def mimeData(self): return Mime()
        def setDropAction(self,action): self.action=action
        def accept(self): self.accepted=True
    class Receiver:
        def add_files(self,files): self.files=files
    event=Event()
    Window.dragEnterEvent(None,event)
    assert event.action==QtCore.Qt.CopyAction and event.accepted
    receiver=Receiver()
    Window.dropEvent(receiver,event)
    assert event.action==QtCore.Qt.CopyAction and event.accepted
    assert len(receiver.files)==1

"""Classic Outlook OLE virtual files, using Windows APIs available before 1607.

IDataObject is consumed synchronously while Drop owns the borrowed COM pointer.
Only copies are requested; STGMEDIUM is always released by its original owner.
No Outlook automation, mailbox changes, clipboard scraping or external services.
"""
import ctypes as C
from dataclasses import dataclass
from pathlib import Path
import os
import struct
import tempfile
import uuid

DWORD = C.c_uint32
LONG = C.c_int32
HRESULT = LONG
ULONG = DWORD
PTR = C.c_void_p
CALL = getattr(C, 'WINFUNCTYPE', C.CFUNCTYPE)
S_OK, S_FALSE = 0, 1
E_NOINTERFACE = -2147467262
E_NOTIMPL = -2147467263
TYMED_HGLOBAL, TYMED_ISTREAM, TYMED_ISTORAGE = 1, 4, 8
COPY = 1
MAX_FILE = 1024 * 1024 * 1024
SUPPORTED = {'.pdf', '.msg', '.eml'}


class GUID(C.Structure):
    _fields_ = [('raw', C.c_ubyte * 16)]

    @classmethod
    def of(cls, text):
        return cls.from_buffer_copy(uuid.UUID(text).bytes_le)


IID_UNKNOWN = GUID.of('00000000-0000-0000-C000-000000000046')
IID_DROP = GUID.of('00000122-0000-0000-C000-000000000046')


class FORMATETC(C.Structure):
    _fields_ = [('cfFormat', C.c_uint16), ('ptd', PTR), ('dwAspect', DWORD),
                ('lindex', LONG), ('tymed', DWORD)]


class STGMEDIUM(C.Structure):
    _fields_ = [('tymed', DWORD), ('handle', PTR), ('pUnkForRelease', PTR)]


class POINTL(C.Structure):
    _fields_ = [('x', LONG), ('y', LONG)]


def method(pointer, index, result, *arguments):
    table = C.cast(pointer, C.POINTER(C.POINTER(PTR))).contents
    return CALL(result, PTR, *arguments)(table[index])


def check(hr, operation):
    if hr < 0:
        raise OSError(f'{operation}: HRESULT 0x{hr & 0xffffffff:08X}')


@dataclass(frozen=True)
class Descriptor:
    name: str
    size: object = None


def descriptors(data, wide=True):
    """FILEDESCRIPTORW is 592 bytes, its ANSI counterpart is 332 bytes."""
    if len(data) < 4:
        raise ValueError('Hiányos Outlook-fájlleíró.')
    count = struct.unpack_from('<I', data)[0]
    stride = 592 if wide else 332
    if count > 1024 or len(data) < 4 + count * stride:
        raise ValueError('Érvénytelen vagy túl nagy Outlook-fájllista.')
    result = []
    for index in range(count):
        offset = 4 + index * stride
        flags = struct.unpack_from('<I', data, offset)[0]
        high, low = struct.unpack_from('<II', data, offset + 64)
        raw = data[offset + 72: offset + stride]
        if wide:
            name = raw.decode('utf-16-le', errors='strict').split('\0', 1)[0]
        else:
            name = raw.split(b'\0', 1)[0].decode('mbcs' if os.name == 'nt' else 'cp1252')
        if not name:
            raise ValueError('Névtelen Outlook-elem.')
        result.append(Descriptor(name, (high << 32 | low) if flags & 0x40 else None))
    return result


class WinAPI:
    def __init__(self):
        if os.name != 'nt':
            raise OSError('A natív Outlook-behúzás csak Windowson érhető el.')
        self.ole = C.WinDLL('ole32', use_last_error=True)
        self.user = C.WinDLL('user32', use_last_error=True)
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        self.shell = C.WinDLL('shell32', use_last_error=True)
        bindings = [
            (self.ole, 'OleInitialize', HRESULT, [PTR]),
            (self.ole, 'OleUninitialize', None, []),
            (self.ole, 'RegisterDragDrop', HRESULT, [PTR, PTR]),
            (self.ole, 'RevokeDragDrop', HRESULT, [PTR]),
            (self.ole, 'ReleaseStgMedium', None, [C.POINTER(STGMEDIUM)]),
            (self.ole, 'StgCreateDocfile', HRESULT, [C.c_wchar_p, DWORD, DWORD, C.POINTER(PTR)]),
            (self.ole, 'ReadClassStg', HRESULT, [PTR, C.POINTER(GUID)]),
            (self.ole, 'WriteClassStg', HRESULT, [PTR, C.POINTER(GUID)]),
            (self.user, 'RegisterClipboardFormatW', C.c_uint, [C.c_wchar_p]),
            (self.kernel, 'GlobalSize', C.c_size_t, [PTR]),
            (self.kernel, 'GlobalLock', PTR, [PTR]),
            (self.kernel, 'GlobalUnlock', C.c_int, [PTR]),
            (self.kernel, 'GlobalAlloc', PTR, [C.c_uint, C.c_size_t]),
            (self.shell, 'DragQueryFileW', C.c_uint, [PTR, C.c_uint, C.c_wchar_p, C.c_uint]),
        ]
        for library, name, result, arguments in bindings:
            function = getattr(library, name)
            function.restype, function.argtypes = result, arguments
        self.formats = {name: self.user.RegisterClipboardFormatW(name) for name in
                        ('FileGroupDescriptorW', 'FileGroupDescriptor', 'FileContents')}
        if not all(self.formats.values()):
            raise OSError('Az Outlook-adatformátumok regisztrálása sikertelen.')

    def global_bytes(self, handle, limit=MAX_FILE):
        size = self.kernel.GlobalSize(handle)
        if size > limit:
            raise ValueError('Az Outlookból átvett adat túl nagy.')
        if not size:
            return b''
        address = self.kernel.GlobalLock(handle)
        if not address:
            raise OSError('Az Outlook-memória nem olvasható.')
        try:
            return C.string_at(address, size)
        finally:
            self.kernel.GlobalUnlock(handle)

    def global_alloc(self, data):
        handle = self.kernel.GlobalAlloc(0x42, max(1, len(data)))
        if not handle:
            raise MemoryError()
        address = self.kernel.GlobalLock(handle)
        C.memmove(address, data, len(data))
        self.kernel.GlobalUnlock(handle)
        return handle

    def get(self, data, format_id, index=-1, media=TYMED_HGLOBAL):
        format_ = FORMATETC(format_id, None, 1, index, media)
        medium = STGMEDIUM()
        hr = method(data, 3, HRESULT, C.POINTER(FORMATETC), C.POINTER(STGMEDIUM))(
            data, C.byref(format_), C.byref(medium))
        check(hr, 'Outlook GetData')
        return medium

    def has(self, data, format_id, media=TYMED_HGLOBAL):
        format_ = FORMATETC(format_id, None, 1, -1, media)
        return method(data, 5, HRESULT, C.POINTER(FORMATETC))(data, C.byref(format_)) == S_OK

    def release_medium(self, medium):
        self.ole.ReleaseStgMedium(C.byref(medium))

    def stream_to_file(self, stream, path):
        # Outlook may return a stream whose cursor is at its last write position.
        # Seek-less streams can still be consumed from their initial position.
        method(stream, 5, HRESULT, C.c_int64, DWORD, PTR)(stream, 0, 0, None)
        buffer = C.create_string_buffer(65536)
        read = ULONG()
        total = 0
        with open(path, 'wb') as destination:
            while True:
                read.value = 0
                hr = method(stream, 3, HRESULT, PTR, ULONG, C.POINTER(ULONG))(
                    stream, buffer, len(buffer), C.byref(read))
                check(hr, 'Outlook IStream.Read')
                if read.value > len(buffer):
                    raise ValueError('Érvénytelen Outlook-adatfolyam.')
                total += read.value
                if total > MAX_FILE:
                    raise ValueError('Az Outlookból átvett fájl túl nagy.')
                destination.write(buffer.raw[:read.value])
                if hr == S_FALSE or read.value == 0:
                    return total

    def storage_to_file(self, source, path):
        destination = PTR()
        # STGM_CREATE | STGM_READWRITE | STGM_SHARE_EXCLUSIVE. Only our tempfile.
        check(self.ole.StgCreateDocfile(str(path), 0x1012, 0, C.byref(destination)), 'MSG másolat létrehozása')
        try:
            check(method(source, 7, HRESULT, DWORD, PTR, PTR, PTR)(
                source, 0, None, None, destination), 'Outlook IStorage.CopyTo')
            clsid = GUID()
            if self.ole.ReadClassStg(source, C.byref(clsid)) >= 0:
                check(self.ole.WriteClassStg(destination, C.byref(clsid)), 'MSG osztályazonosító másolása')
            check(method(destination, 9, HRESULT, DWORD)(destination, 0), 'MSG másolat véglegesítése')
        finally:
            method(destination, 2, ULONG)(destination)


class Receiver:
    def __init__(self, staging, api=None):
        self.api = api or WinAPI()
        self.staging = Path(staging)

    def accepts(self, data):
        return any(self.api.has(data, format_id) for format_id in
                   (self.api.formats['FileGroupDescriptorW'], self.api.formats['FileGroupDescriptor'], 15))

    def files(self, data):
        api = self.api
        # Explorer and Outlook versions exposing actual files retain normal import.
        if api.has(data, 15):
            medium = api.get(data, 15)
            try:
                count = api.shell.DragQueryFileW(medium.handle, 0xffffffff, None, 0)
                paths = []
                for index in range(count):
                    length = api.shell.DragQueryFileW(medium.handle, index, None, 0)
                    name = C.create_unicode_buffer(length + 1)
                    api.shell.DragQueryFileW(medium.handle, index, name, length + 1)
                    if Path(name.value).suffix.lower() in SUPPORTED:
                        paths.append(Path(name.value))
                if paths:
                    return paths, []
            finally:
                api.release_medium(medium)
        wide = api.has(data, api.formats['FileGroupDescriptorW'])
        medium = api.get(data, api.formats['FileGroupDescriptorW' if wide else 'FileGroupDescriptor'])
        try:
            entries = descriptors(api.global_bytes(medium.handle, 4 + 1024 * 592), wide)
        finally:
            api.release_medium(medium)
        paths, errors = [], []
        for index, entry in enumerate(entries):
            suffix = Path(entry.name).suffix.lower()
            if suffix not in SUPPORTED:
                continue
            path = None
            try:
                if entry.size is not None and entry.size > MAX_FILE:
                    raise ValueError('A fájl meghaladja az 1 GiB-os átvételi korlátot.')
                medium = None
                last_error = None
                for media in (13, TYMED_ISTREAM, TYMED_ISTORAGE, TYMED_HGLOBAL):
                    try:
                        medium = api.get(data, api.formats['FileContents'], index, media)
                        break
                    except OSError as error:
                        last_error = error
                if medium is None:
                    raise last_error
                try:
                    handle, filename = tempfile.mkstemp(prefix='outlook-', suffix=suffix, dir=self.staging)
                    os.close(handle)
                    path = Path(filename)
                    if medium.tymed == TYMED_ISTREAM:
                        size = api.stream_to_file(medium.handle, path)
                    elif medium.tymed == TYMED_ISTORAGE:
                        if suffix != '.msg':
                            raise ValueError('IStorage formátum csak MSG-üzenethez fogadható el.')
                        api.storage_to_file(medium.handle, path)
                        size = None  # Re-serialization may change the compound-file size.
                    elif medium.tymed == TYMED_HGLOBAL:
                        content = api.global_bytes(medium.handle)
                        if entry.size is not None:
                            if len(content) < entry.size:
                                raise ValueError('Hiányos Outlook-fájltartalom.')
                            content = content[:entry.size]
                        path.write_bytes(content)
                        size = len(content)
                    else:
                        raise ValueError('Nem támogatott Outlook-adatátadási mód.')
                    if size is not None and entry.size is not None and size != entry.size:
                        raise ValueError('Az átvett Outlook-fájl mérete nem egyezik a leíróval.')
                    if path.stat().st_size > MAX_FILE:
                        raise ValueError('Az Outlookból átvett fájl túl nagy.')
                    if path.stat().st_size == 0:
                        raise ValueError('Üres Outlook-fájltartalom.')
                    paths.append(path)
                finally:
                    api.release_medium(medium)
            except Exception as error:
                if path is not None:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass  # Staging cleanup is retried on normal application exit.
                errors.append(f'{entry.name}: {error}')
        if not paths and not errors:
            errors.append('A behúzott elemek között nincs PDF-, MSG- vagy EML-dokumentum.')
        return paths, errors


class COMObject(C.Structure):
    _fields_ = [('vtable', C.POINTER(PTR))]


class DropTarget:
    """A strongly retained, apartment-bound native IDropTarget implementation."""
    def __init__(self, receiver, deliver):
        self.receiver, self.deliver = receiver, deliver
        self.references = 1
        self.accepted = False
        signatures = [
            (HRESULT, [PTR, C.POINTER(GUID), C.POINTER(PTR)], self.query),
            (ULONG, [PTR], self.add_ref), (ULONG, [PTR], self.release),
            (HRESULT, [PTR, PTR, DWORD, POINTL, C.POINTER(DWORD)], self.enter),
            (HRESULT, [PTR, DWORD, POINTL, C.POINTER(DWORD)], self.over),
            (HRESULT, [PTR], self.leave),
            (HRESULT, [PTR, PTR, DWORD, POINTL, C.POINTER(DWORD)], self.drop),
        ]
        self.callbacks = [CALL(result, *args)(function) for result, args, function in signatures]
        self.table = (PTR * len(self.callbacks))(*[C.cast(fn, PTR).value for fn in self.callbacks])
        self.object = COMObject(self.table)
        self.pointer = C.cast(C.pointer(self.object), PTR)

    def query(self, this, iid, result):
        result[0] = None
        if bytes(iid.contents) in (bytes(IID_UNKNOWN), bytes(IID_DROP)):
            result[0] = this
            self.references += 1
            return S_OK
        return E_NOINTERFACE

    def add_ref(self, this):
        self.references += 1
        return self.references

    def release(self, this):
        self.references = max(0, self.references - 1)
        return self.references

    def enter(self, this, data, keys, point, effect):
        try:
            self.accepted = self.receiver.accepts(data)
        except Exception:
            self.accepted = False
        effect[0] = COPY if self.accepted and effect[0] & COPY else 0
        return S_OK

    def over(self, this, keys, point, effect):
        effect[0] = COPY if self.accepted and effect[0] & COPY else 0
        return S_OK

    def leave(self, this):
        self.accepted = False
        return S_OK

    def drop(self, this, data, keys, point, effect):
        allowed = bool(effect[0] & COPY)
        effect[0] = 0
        try:
            if allowed:
                paths, errors = self.receiver.files(data)
                # deliver must enqueue a Qt signal; never show a modal dialog in Drop.
                self.deliver(paths, errors)
                effect[0] = COPY if paths else 0
        except Exception as error:
            self.deliver([], [f'Az Outlook-behúzás sikertelen: {error}'])
        self.accepted = False
        return S_OK


class NativeDrops:
    def __init__(self, widgets, staging, deliver):
        from PyQt5 import QtCore
        self.api = WinAPI()
        self.handles, self.targets = [], []
        self.initialized = False
        check(self.api.ole.OleInitialize(None), 'OLE inicializálása (STA szükséges)')
        self.initialized = True
        self.receiver = Receiver(staging, self.api)
        try:
            for widget in widgets:
                widget.setAcceptDrops(False)
                widget.setAttribute(QtCore.Qt.WA_NativeWindow, True)
                handle = int(widget.winId())
                if handle in self.handles:
                    continue
                target = DropTarget(self.receiver, deliver)
                check(self.api.ole.RegisterDragDrop(handle, target.pointer), 'Outlook drop target regisztrálása')
                self.handles.append(handle)
                self.targets.append(target)
        except Exception:
            self.close()
            raise

    def close(self):
        for handle in reversed(self.handles):
            self.api.ole.RevokeDragDrop(handle)
        self.handles.clear()
        self.targets.clear()
        if self.initialized:
            self.api.ole.OleUninitialize()
            self.initialized = False

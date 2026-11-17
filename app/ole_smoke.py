"""Synthetic native OLE acceptance checks; contains no Outlook/customer data.

Exercises real Windows HGLOBAL/IStream/IStorage and IDropTarget vtables. It is
not a claim that a particular Outlook release or physical mouse drag was tested.
"""
import ctypes as C
from email.message import EmailMessage
from pathlib import Path
import struct
import tempfile
from .windows_drop import (WinAPI, FORMATETC, STGMEDIUM, PTR, DWORD, ULONG, HRESULT,
                           GUID, CALL, COMObject, DropTarget, Receiver, POINTL,
                           method, check, COPY, TYMED_HGLOBAL, TYMED_ISTREAM,
                           TYMED_ISTORAGE, IID_UNKNOWN)
from .documents import import_files


def write_stream(storage, name, data):
    stream = PTR()
    check(method(storage, 3, HRESULT, C.c_wchar_p, DWORD, DWORD, DWORD, C.POINTER(PTR))(
        storage, name, 0x1012, 0, 0, C.byref(stream)), 'Synthetic CreateStream')
    try:
        written = ULONG()
        check(method(stream, 4, HRESULT, PTR, ULONG, C.POINTER(ULONG))(
            stream, C.c_char_p(data), len(data), C.byref(written)), 'Synthetic Write')
        assert written.value == len(data)
    finally:
        method(stream, 2, ULONG)(stream)


def prop(tag, value):
    return struct.pack('<II', tag, 6) + struct.pack('<Q', value)


def make_message(api, path, pdf):
    root = PTR()
    check(api.ole.StgCreateDocfile(str(path), 0x1012, 0, C.byref(root)), 'Synthetic MSG')
    try:
        clsid = GUID.of('00020D0B-0000-0000-C000-000000000046')
        check(api.ole.WriteClassStg(root, C.byref(clsid)), 'Synthetic MSG CLSID')
        named = PTR()
        check(method(root, 5, HRESULT, C.c_wchar_p, DWORD, DWORD, DWORD, C.POINTER(PTR))(
            root, '__nameid_version1.0', 0x1012, 0, 0, C.byref(named)), 'Synthetic named properties')
        try:
            for stream_name in ('__substg1.0_00020102', '__substg1.0_00030102', '__substg1.0_00040102'):
                write_stream(named, stream_name, b'')
            check(method(named,9,HRESULT,DWORD)(named,0),'Synthetic named properties commit')
        finally:
            method(named,2,ULONG)(named)
        write_stream(root, '__properties_version1.0',
                     b'\0'*8 + struct.pack('<IIII',0,1,0,1) + b'\0'*8 + prop(0x340D0003,0x40000))
        write_stream(root, '__substg1.0_001A001F', 'IPM.Note\0'.encode('utf-16-le'))
        write_stream(root, '__substg1.0_0037001F', 'Synthetic message\0'.encode('utf-16-le'))
        attachment = PTR()
        check(method(root, 5, HRESULT, C.c_wchar_p, DWORD, DWORD, DWORD, C.POINTER(PTR))(
            root, '__attach_version1.0_#00000000', 0x1012, 0, 0, C.byref(attachment)), 'Synthetic attachment')
        try:
            name = 'szintetikus.pdf\0'.encode('utf-16-le')
            write_stream(attachment, '__properties_version1.0', b'\0'*8 +
                         prop(0x37050003,1) + prop(0x3707001F,len(name)) + prop(0x37010102,len(pdf)))
            write_stream(attachment, '__substg1.0_3707001F', name)
            write_stream(attachment, '__substg1.0_37010102', pdf)
            check(method(attachment,9,HRESULT,DWORD)(attachment,0),'Synthetic attachment commit')
        finally:
            method(attachment,2,ULONG)(attachment)
        check(method(root,9,HRESULT,DWORD)(root,0),'Synthetic MSG commit')
    finally:
        method(root,2,ULONG)(root)
    api.ole.StgOpenStorage.argtypes = [C.c_wchar_p,PTR,DWORD,PTR,DWORD,C.POINTER(PTR)]
    api.ole.StgOpenStorage.restype = HRESULT
    root = PTR()
    check(api.ole.StgOpenStorage(str(path),None,0x20,None,0,C.byref(root)), 'Synthetic read-only MSG')
    return root


def descriptor_group(entries):
    result = bytearray(struct.pack('<I',len(entries)))
    for name, medium, content in entries:
        row = bytearray(592)
        if medium != TYMED_ISTORAGE:
            struct.pack_into('<I',row,0,0x40)
            struct.pack_into('<II',row,64,0,len(content))
        encoded = (name + '\0').encode('utf-16-le')
        row[72:72+len(encoded)] = encoded
        result.extend(row)
    return bytes(result)


class SyntheticDataObject:
    """Provides the actual IDataObject ABI to the production drop target."""
    def __init__(self, api, entries=(), paths=()):
        self.api, self.entries, self.paths = api, entries, paths
        self.refs, self.failures = 1, []
        unknown = CALL(HRESULT,PTR)(lambda this: -2147467263)
        self.callbacks = [
            CALL(HRESULT,PTR,C.POINTER(GUID),C.POINTER(PTR))(self.query),
            CALL(ULONG,PTR)(self.add_ref), CALL(ULONG,PTR)(self.release),
            CALL(HRESULT,PTR,C.POINTER(FORMATETC),C.POINTER(STGMEDIUM))(self.get),
            unknown, CALL(HRESULT,PTR,C.POINTER(FORMATETC))(self.query_data),
        ] + [unknown]*6
        self.table=(PTR*12)(*[C.cast(fn,PTR).value for fn in self.callbacks])
        self.object=COMObject(self.table)
        self.pointer=C.cast(C.pointer(self.object),PTR)

    def query(self,this,iid,out):
        out[0]=None
        if bytes(iid.contents) in (bytes(IID_UNKNOWN),bytes(GUID.of('0000010e-0000-0000-C000-000000000046'))):
            out[0]=this
            self.refs+=1
            return 0
        return -2147467262

    def add_ref(self,this):
        self.refs+=1
        return self.refs

    def release(self,this):
        self.refs-=1
        return self.refs

    def query_data(self,this,format_):
        f=format_.contents
        if self.paths and f.cfFormat==15 and f.tymed & 1:
            return 0
        if self.entries and f.cfFormat==self.api.formats['FileGroupDescriptorW'] and f.tymed & 1:
            return 0
        if f.cfFormat==self.api.formats['FileContents'] and 0<=f.lindex<len(self.entries):
            if f.tymed & self.entries[f.lindex][1]:
                return 0
        return -2147221404  # DV_E_FORMATETC

    def get(self,this,format_,out):
        if self.query_data(this,format_)!=0:
            return -2147221404
        try:
            f=format_.contents
            out.contents.pUnkForRelease=None
            if f.cfFormat==15:
                payload=struct.pack('<IiiII',20,0,0,0,1)+('\0'.join(map(str,self.paths))+'\0\0').encode('utf-16-le')
                out.contents.tymed=TYMED_HGLOBAL
                out.contents.handle=self.api.global_alloc(payload)
            elif f.cfFormat==self.api.formats['FileGroupDescriptorW']:
                out.contents.tymed=TYMED_HGLOBAL
                out.contents.handle=self.api.global_alloc(descriptor_group(self.entries))
            else:
                name,media,content=self.entries[f.lindex]
                out.contents.tymed=media
                if media==TYMED_HGLOBAL:
                    out.contents.handle=self.api.global_alloc(content)
                elif media==TYMED_ISTORAGE:
                    method(content,1,ULONG)(content)
                    out.contents.handle=content.value
                else:
                    self.api.ole.CreateStreamOnHGlobal.argtypes=[PTR,C.c_int,C.POINTER(PTR)]
                    self.api.ole.CreateStreamOnHGlobal.restype=HRESULT
                    stream=PTR()
                    check(self.api.ole.CreateStreamOnHGlobal(None,1,C.byref(stream)),'Synthetic IStream')
                    written=ULONG()
                    check(method(stream,4,HRESULT,PTR,ULONG,C.POINTER(ULONG))(
                        stream,C.c_char_p(content),len(content),C.byref(written)),'Synthetic stream write')
                    # Intentionally leave the stream at EOF: the receiver must rewind it.
                    out.contents.handle=stream.value
            return 0
        except Exception as error:
            self.failures.append(str(error))
            return -2147467259


def run_native_cases(staging, pdf):
    api=WinAPI()
    check(api.ole.OleInitialize(None),'Synthetic OLE initialization')
    try:
        with tempfile.TemporaryDirectory(prefix='neak-ole-fixture-') as folder:
            root=Path(folder)
            source=root/'source.msg'
            storage=make_message(api,source,pdf)
            original=source.read_bytes()
            try:
                message=EmailMessage()
                message.set_content('Synthetic message')
                message.add_attachment(pdf,maintype='application',subtype='pdf',filename='test.pdf')
                eml=message.as_bytes()
                cases=[
                    ('one PDF HGLOBAL',[('egy.pdf',1,pdf)],1),
                    ('multiple PDF IStream',[('egy.pdf',4,pdf),('kettő.pdf',4,pdf)],2),
                    ('one email IStorage',[('levél.msg',8,storage)],1),
                    ('multiple email IStorage',[('egy.msg',8,storage),('kettő.msg',8,storage)],2),
                    ('mixed PDF and email IStream',[('vegyes.pdf',4,pdf),('levél.msg',4,original)],2),
                    ('email HGLOBAL',[('levél.msg',1,original)],1),
                    ('EML HGLOBAL',[('levél.eml',1,eml)],1),
                ]
                all_pdfs=[]
                for title,entries,expected in cases:
                    incoming=SyntheticDataObject(api,entries)
                    delivered=[]
                    target=DropTarget(Receiver(staging,api),lambda paths,errors: delivered.append((paths,errors)))
                    effect=DWORD(3)
                    check(method(target.pointer,3,HRESULT,PTR,DWORD,POINTL,C.POINTER(DWORD))(
                        target.pointer,incoming.pointer,0,POINTL(),C.byref(effect)),title+' DragEnter')
                    assert effect.value==COPY,title
                    check(method(target.pointer,6,HRESULT,PTR,DWORD,POINTL,C.POINTER(DWORD))(
                        target.pointer,incoming.pointer,0,POINTL(),C.byref(effect)),title+' Drop')
                    assert effect.value==COPY and len(delivered)==1,title
                    paths,errors=delivered[0]
                    assert not errors and not incoming.failures,(title,errors,incoming.failures)
                    assert len(paths)==len(entries),title
                    pdfs=import_files(paths,staging)
                    assert len(pdfs)==expected,(title,pdfs)
                    assert all(path.read_bytes()==pdf for path in pdfs),title
                    assert source.read_bytes()==original,'Source message changed'
                    all_pdfs.extend(pdfs)
                    print('PASS: native OLE '+title)
                # Actual CF_HDROP must still work on the same native drop target.
                local_pdf=root/'normal.pdf'; local_pdf.write_bytes(pdf)
                local_eml=root/'normal.eml'; local_eml.write_bytes(eml)
                incoming=SyntheticDataObject(api,paths=[local_pdf,source,local_eml])
                paths,errors=Receiver(staging,api).files(incoming.pointer)
                assert not errors and len(import_files(paths,staging))==3
                print('PASS: native CF_HDROP PDF/MSG/EML regression')
                return all_pdfs
            finally:
                method(storage,2,ULONG)(storage)
    finally:
        api.ole.OleUninitialize()

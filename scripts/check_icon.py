"""Verify the actual PE RT_GROUP_ICON/RT_ICON bytes against our seven-size ICO."""
from pathlib import Path
import struct
import sys
import pefile


def check(executable,ico_path):
    source=Path(ico_path).read_bytes()
    reserved,kind,count=struct.unpack_from('<HHH',source)
    assert (reserved,kind)==(0,1)
    expected={}
    for i in range(count):
        width,height,colors,reserved,planes,bits,size,offset=struct.unpack_from('<BBBBHHII',source,6+16*i)
        expected[width or 256]=source[offset:offset+size]
    assert set(expected)=={16,24,32,48,64,128,256}
    with pefile.PE(executable) as pe:
        images={};groups=[]
        for kind in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if kind.id not in (3,14):continue
            for entry in kind.directory.entries:
                for language in entry.directory.entries:
                    data=language.data.struct
                    content=pe.get_data(data.OffsetToData,data.Size)
                    if kind.id==3:images[entry.id]=content
                    else:groups.append(content)
        assert groups,'EXE has no RT_GROUP_ICON'
        matched=False
        for group in groups:
            found={}
            _,_,count=struct.unpack_from('<HHH',group)
            for i in range(count):
                width,height,colors,reserved,planes,bits,size,identifier=struct.unpack_from('<BBBBHHIH',group,6+14*i)
                found[width or 256]=images[identifier]
            if found==expected:matched=True
        assert matched,'EXE icon resources differ from the supplied application.ico'
    print('PASS: actual EXE embeds the custom 16/24/32/48/64/128/256 icon bytes')


if __name__=='__main__':check(sys.argv[1],sys.argv[2])

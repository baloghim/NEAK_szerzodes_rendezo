"""Check the actual packaged Windows executable's requested privilege level."""
import sys
import xml.etree.ElementTree as ET
import pefile  # Windows PyInstaller build dependency, not an app dependency.


def main():
    with pefile.PE(sys.argv[1]) as executable:
        manifests = []
        for kind in executable.DIRECTORY_ENTRY_RESOURCE.entries:
            if kind.id != 24:  # RT_MANIFEST
                continue
            for resource in kind.directory.entries:
                for language in resource.directory.entries:
                    item = language.data.struct
                    manifests.append(executable.get_data(item.OffsetToData, item.Size))
        assert manifests, 'Executable has no manifest'
        for manifest in manifests:
            root = ET.fromstring(manifest)
            levels = root.findall('.//{urn:schemas-microsoft-com:asm.v3}requestedExecutionLevel')
            assert len(levels) == 1
            assert levels[0].attrib == {'level': 'asInvoker', 'uiAccess': 'false'}, levels[0].attrib
    print('PASS: packaged EXE manifest is asInvoker, uiAccess=false')


if __name__ == '__main__':
    main()

"""Run on a Windows test share with synthetic bytes only."""
from pathlib import Path
import sys
import os
import tempfile
from app.core import Store, save_copy


def main():
    share = Path(sys.argv[1])
    if os.name != 'nt' or not str(share).startswith('\\\\'):
        raise RuntimeError('This check requires a real Windows UNC path')
    if not share.is_dir():
        raise RuntimeError('The UNC share is not reachable')
    with tempfile.TemporaryDirectory(prefix='neak-unc-') as local:
        root = Path(local)
        source = root/'source.pdf'
        source.write_bytes(b'%PDF-1.4\n% synthetic network copy test\n%%EOF')
        store = Store(root/'index.sqlite3')
        target = share/'synthetic-contract.pdf'
        try:
            save_copy(source, target, store)
            assert source.read_bytes() == target.read_bytes()
            try:
                save_copy(source, target, store, True)
            except FileExistsError:
                pass
            else:
                raise AssertionError('Existing network file was overwritten')
            store.mark(target, 'Feltöltve')
            store.db.close()
            store = Store(root/'index.sqlite3')
            assert store.status(target)[0] == 'Feltöltve'
            assert store.status(target)[1]
            assert source.exists()
            print('PASS: Windows SMB/UNC copy, overwrite protection, persistent status')
        finally:
            store.db.close()
            target.unlink(missing_ok=True)


if __name__ == '__main__':
    main()

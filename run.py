import sys

if __name__ == '__main__':
    if '--self-test' in sys.argv:
        import json
        import traceback
        from pathlib import Path
        try:
            from app.selftest import run
            code = run()
            result = {'passed': code == 0}
        except Exception:
            code = 1
            result = {'passed': False, 'error': traceback.format_exc()}
        Path('self-test-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        sys.exit(code)
    from app.gui import main
    main()

import sys

if __name__ == '__main__':
    if '--self-test' in sys.argv:
        from app.selftest import run
        sys.exit(run())
    from app.gui import main
    main()

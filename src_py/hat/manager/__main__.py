import sys

from hat.manager.main import main


if __name__ == '__main__':
    sys.argv[0] = 'hat-manager'
    sys.exit(main())

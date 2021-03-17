import sys

from hat.event.server.main import main


if __name__ == '__main__':
    sys.argv[0] = 'hat-event'
    sys.exit(main())

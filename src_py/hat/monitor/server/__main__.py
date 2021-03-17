import sys

from hat.monitor.server.main import main


if __name__ == '__main__':
    sys.argv[0] = 'hat-monitor'
    sys.exit(main())

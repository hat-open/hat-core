import sys

from hat.gateway.main import main


if __name__ == '__main__':
    sys.argv[0] = 'hat-gateway'
    sys.exit(main())

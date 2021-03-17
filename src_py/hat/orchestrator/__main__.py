import sys

from hat.orchestrator.main import main


if __name__ == '__main__':
    sys.argv[0] = 'hat-orchestrator'
    sys.exit(main())

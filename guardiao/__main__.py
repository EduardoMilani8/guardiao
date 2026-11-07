"""`python -m guardiao ...` ainda funciona: repassa tudo para `python -m guarnicao`."""

import sys

from guarnicao.__main__ import main

if __name__ == "__main__":
    sys.exit(main())

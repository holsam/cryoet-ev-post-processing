'''
Commands: license
'''
# -- Import external dependencies ----------------
import typer
from rich import print

# -- Define printLicense command -----------------
def printLicense():
    with open('LICENSE', 'r') as licensefile:
        print(f"\n{licensefile.read()}")
    typer.Exit(0)

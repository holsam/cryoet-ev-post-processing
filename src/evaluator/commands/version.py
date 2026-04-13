'''
Commands: version
'''
# -- Import external dependencies ----------------
import tomllib, typer
from rich import print

# -- Define printVersion command -----------------
def printVersion():
    with open('pyproject.toml', 'rb') as f:
        contents = tomllib.load(f)
    print(f"\nRunning EValuator version: v{contents['project']['version']}\n")
    typer.Exit(0)
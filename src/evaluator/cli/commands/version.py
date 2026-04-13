'''
CLI command: version
'''
# -- Import external dependencies ----------------
import typer

# -- Import internal EValuator functions and variables
import evaluator.commands.version as versionFuncs

# -- Initialiate Typer class for license command -
evaluatorVersion = typer.Typer(
    # Disable --install-completion and --show-completion options in terminal
    add_completion=False,
    # Disable --help option in terminal
    add_help_option=False
)

# -- Define license command ----------------------
@evaluatorVersion.command(rich_help_panel="Utility Commands")
def version():
    '''
    Print current EValuator version to terminal and exit
    '''
    versionFuncs.main()
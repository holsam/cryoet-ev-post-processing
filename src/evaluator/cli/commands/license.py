'''
CLI command: license
'''
# -- Import external dependencies ----------------
import typer

# -- Import internal EValuator functions and variables
import evaluator.commands.license as licenseFuncs

# -- Initialiate Typer class for license command -
evaluatorLicense = typer.Typer(
    # Disable --install-completion and --show-completion options in terminal
    add_completion=False,
    # Disable --help option in terminal
    add_help_option=False
)

# -- Define license command ----------------------
@evaluatorLicense.command(rich_help_panel="Utility Commands")
def license():
    '''
    Print EValuator license to terminal and exit
    '''
    licenseFuncs.printLicense()
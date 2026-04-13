'''
Utility Functions: config management
'''

# -- Import external dependencies ----------------
import tomli_w, tomllib
from importlib.resources import files as pkg_files
from pathlib import Path
from platformdirs import user_config_dir
from rich import Console
from rich.table import Table

# -- Define userConfigPath function --------------
def userConfigPath() -> Path:
    '''
    Returns the file path <OS config directory>/evaluator/config.toml depending on the OS of running environment:
        Linux/macOS : ~/.config/evaluator/config.toml
        Windows     : %APPDATA%\\evaluator\\config.toml
    '''
    return Path(user_config_dir("evaluator"), "config.toml")

# -- Define loadDefaultConfig function -----------
def loadDefaultConfig() -> dict:
    '''
    Load the bundled default config.toml from the installed package.
    '''    
    with pkg_files('evaluator').joinpath('config.toml').open('rb') as defaultconfig:
        return tomllib.load(defaultconfig)
    
# -- Define loadUserConfig function --------------
def loadUserConfig() -> dict:
    '''
    TODO
    '''
    config_path = userConfigPath()
    if not config_path.exists():
        raise FileNotFoundError(f"No user config file found at {config_path}.")
    with config_path.open('rb') as f:
        return tomllib.load(f)

# -- Define writeUserConfig function -------------
def writeUserConfig(config: dict) -> None:
    '''
    Write the provided dictionary to a toml file at the supplied file path.
    '''
    config_path = userConfigPath()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open('wb') as f:
        tomli_w.dump(config, f)

# -- Define internalConfigCheck function ---------
def internalConfigCheck(config_path: Path, exists: bool = True) -> bool:
    # Should the function check if the file exists?
    if exists:
        # Does the file exist?
        if config_path.exists():
            # If yes and yes, return nothing: all good!
            return True
        else:
            # If yes and no, return warning that file doesn't exist
            print(
                f'\n[bold yellow]Warning:[/bold yellow] No user config file exists at [cyan]{config_path}[/cyan]\nRun [bold]evaluator config init[/bold] to create a configuration file with default settings.\n'
            )
            return False
    # Or should it check that the file DOESN'T exist?
    else:
        # Does the file exist?
        if config_path.exists():
            # If checking doesn't exist and it does, return warning that file exists
            print(
                f'\n[bold yellow]Warning:[/bold yellow] User config file already exists at [cyan]{config_path}[/cyan]\nRun [bold]evaluator config reset[/bold] to reset configuration to default settings.\n'
            )
            return False
        else:
            # If checking doesn't exist and it doesn't, return nothing: all good!
            return True

# -- Define printConfigTable function ------------
def printConfigTable(user_config: dict, default_config: dict) -> None:
    '''
    Print a rich table comparing user config values against bundled defaults.
    Rows where the user value differs from the default are highlighted.
    '''
    # Set up rich console
    console = Console()
    # Define layout of rich table
    table = Table(
        title="EValuator configuration",
        show_header=True,
        header_style="bold",
        show_lines=False,
    )
    # Add columns to rich table
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Current value", justify="right")
    table.add_column("Default value", justify="right", style="dim")
    table.add_column("", width=2)    # status column
    # Loop through each key in default config
    for key in sorted(default_config.keys()):
        # Extract default and user values
        default_val = default_config[key]
        user_val = user_config.get(key, "[bold red]MISSING[/bold red]")
        # Work out if user option is different to default
        changed = str(user_val) != str(default_val)
        status = "[yellow]≠[/yellow]" if changed else "[green]✓[/green]"
        user_str = f"[yellow]{user_val}[/yellow]" if changed else str(user_val)
        # Add row to table
        table.add_row(key, user_str, str(default_val), status)
    # Print table
    console.print(table)
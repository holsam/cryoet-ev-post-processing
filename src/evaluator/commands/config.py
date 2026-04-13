'''
Functions: configuration management
'''

# -- Import external dependencies ----------------
import tomllib, typer
from rich import print

# -- Import internal EValuator functions and variables
import evaluator.utils.config_management as utilsconf
import evaluator.utils.file_handling as utilsfile

# -- Define config_init function -----------------
def config_init():
    # Get path to user config file
    config_path = utilsconf.userConfigPath()
    # Check if file already exists
    if not utilsconf.internalConfigCheck(config_path, exists=False):
        raise typer.Exit(1)
    try:
        # Load default config from bundled toml file
        defaults = utilsconf.loadDefaultConfig()
        # Write default config to user config file path
        utilsconf.writeUserConfig(defaults)
        # Print success message
        print(
            f'[bold green]SUCCESS:[/bold green] User config file written to [cyan]{config_path}[/cyan]\n'
        )
    except Exception as e:
        # Print error message
        print(
            f'[bold red]ERROR:[/bold red] Failed to write user config file to [cyan]{config_path}[/cyan]: {e}.\n'
        )
        raise typer.Exit(1)

# -- Define config_exists function ---------------
def config_exists() -> None:
    '''
    Report whether a user config file exists and the expected file path.
    '''
    # Get path to user config file
    config_path = utilsconf.userConfigPath()
    # If file exists:
    if config_path.exists():
        # Print success message
        print(
            f"[bold green]SUCCESS:[/bold green]User config file found at [cyan]{config_path}[/cyan]\n"
        )
    else:
        # Otherwise, print warning
        print(f'[bold yellow]WARNING:[/bold yellow] No user config file found at [cyan]{config_path}[/cyan]\nRun [bold]evaluator config init[/bold] to create one.\n')
        raise typer.Exit(1)


# -- Define config_list function -----------------
def config_list() -> None:
    '''
    Print the current config values, highlighting any user values which differ from EValuator defaults.
    '''
    # Get path to user config file
    config_path = utilsconf.userConfigPath()
    # Load default config
    try:
        default_config = utilsfile.flattenToml(utilsconf.loadDefaultConfig())
    except tomllib.TOMLDecodeError as e:
        # Print error
        print(
            f'[bold red]ERROR:[/bold red] Could not parse default config file: {e}.\n'
        )
        raise typer.Exit(1)
    # Check if user config file already exists
    if utilsconf.internalConfigCheck(config_path, exists=True):
        print(
            f'[bold blue]Current config settings:[/bold blue] user config file ([cyan]{config_path}[/cyan]).\n'
        )
        try:
            # Use user config files:
            user_config = utilsconf.loadUserConfig()
        except tomllib.TOMLDecodeError as e:
            # Print error
            print(
                f'[bold red]ERROR:[/bold red] Could not parse user config file: {e}.\n'
            )
            raise typer.Exit(1)
        current_config = utilsfile.flattenToml(user_config)
    else:
        print(f'[bold blue]Current config settings:[/bold blue] default config file.\n')
        current_config = default_config
    utilsconf.printConfigTable(current_config, default_config)
    print()

# -- Define config_verify function ---------------
def config_verify() -> None:
    '''
    Verifies that all expected keys are present in the current user config file by checking against the bundled default config file. Exits with non-zero code if missing or unexpected keys are found.
    '''
    # Get path to user config file
    config_path = utilsconf.userConfigPath()
    # Check user config file exits
    if not utilsconf.internalConfigCheck(config_path, exists=True):
        raise typer.Exit(1)
    try:
        user_config = utilsfile.flattenToml(utilsconf.loadUserConfig())
        default_config = utilsfile.flattenToml(utilsconf.loadDefaultConfig())
    except tomllib.TOMLDecodeError as e:
        # Print error
        print(
            f'[bold red]ERROR:[/bold red] Could not parse config file: {e}.\n'
        )
        raise typer.Exit(1)
    missing = [k for k in default_config if k not in user_config]
    unexpected = [k for k in user_config if k not in default_config]
    issues = missing or unexpected
    if not issues:
        print(
            f'[bold green]SUCCESS:[/bold green] User config file ([cyan]{config_path}[/cyan]) is valid.\n'
        )
        return
    if missing:
        print(
            f'[bold red]ERROR:[/bold red] Found {len(missing)} missing keys in user config file ([cyan]{config_path}[/cyan]):'
        )
        for k in sorted(missing):
            print(
                f'\t[red]✗[/red] {k} [dim](expected: {default_config[k]})[/dim]'
            )
    if unexpected:
        print(
            f'[bold red]ERROR:[/bold red] Found {len(unexpected)} unexpected keys in user config file ([cyan]{config_path}[/cyan]):'
        )
        for k in sorted(unexpected):
            print(
                f'\t[red]?[/red] {k}: {user_config[k]}'
            )
    print(
        f'Run [bold]evaluator config reset[/bold] to reset user configuration file with default values.\n'
    )
    raise typer.Exit(1)

# -- Define config_reset function ----------------
def config_reset(f: bool) -> None:
    '''
    Overwrites the users config file with EValuator's built-in default values.
    Includes a confirmation prompt unless --force supplied.
    '''
    # Get path to config.toml file for user OS
    config_path = utilsconf.userConfigPath()
    # if --force flag wasn't provided:
    if not f:
        print(f'\n[bold yellow]WARNING:[/bold yellow] This will overwrite [cyan]{config_path}[/cyan] with the EValuator default values.')
        confirm = typer.confirm(f'All custom settings will be lost. Continue?')
        if not confirm:
            print("[dim]Reset cancelled.[/dim]\n")
            raise typer.Exit(0)
    try:
        defaults = utilsconf.loadDefaultConfig()
        utilsconf.writeUserConfig(defaults)
    except Exception as e:
        print(f"\n[bold red]Error:[/bold red] Failed to reset user config file at [cyan]{config_path}[/cyan]: {e}")
        raise typer.Exit(1)
    print(f'\n[bold green]SUCCESS:[/bold green] User config file [cyan]{config_path}[/cyan] reset to defaults.\n')
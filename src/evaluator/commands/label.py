import typer

evaluatorLabel = typer.Typer(
    # Disable --install-completion and --show-completion options in terminal
    add_completion=False
)

@evaluatorLabel.command(rich_help_panel="Commands")
def label():
    '''
    Description: labels a cryo-ET tomogram with EV segmentations as analysed using the analyse command
    '''
    print(f"Label command started...")

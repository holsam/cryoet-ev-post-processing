import typer

evaluatorVisualise = typer.Typer(
    # Disable --install-completion and --show-completion options in terminal
    add_completion=False
)

@evaluatorVisualise.command(rich_help_panel="Commands")
def visualise():
    '''
    Description: generate visualisations of tomogram data.
    '''
    print(f"Visualise command started...")

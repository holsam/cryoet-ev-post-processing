'''
=======================================
EValuator: SEGMENTATION EV LABELLING
=======================================
'''
# ====================
# Import external dependencies
# ====================
import typer
from pathlib import Path
from typing import Annotated

# ====================
# Import EValuator utilities
# ====================
from evaluator.commands import label as labelFuncs

# ====================
# Initialise typer as evaluatorLabel
# ====================
evaluatorLabel = typer.Typer(
    add_completion=False,
)

# ====================
# Define command: label
# ====================
@evaluatorLabel.command(   help='Label connected components in a segmentation MRC',rich_help_panel='Component Identification')
def label(
    # Define segmentation argument: path to a binary segmentation MRC file
    input: Annotated[
        Path,
        typer.Option(
            "-i", "--input",
            help="Path to either a binary segmentation MRC (e.g. MemBrain-seg output), or a directory containing binary segmentation MRCs.",
            exists=True,
            file_okay=True,
            dir_okay=True,
            readable=True,
        )
    ],
    # Define output option: output directory, defaults to current working directory
    output: Annotated[
        Path | None,
        typer.Option(
            "-o", "--out-dir",
            help="Path to output directory. The labelled MRC will be written under '.../evaluator/results/label/'.",
            file_okay=False,
            dir_okay=True,
            writable=True,
        )
    ] = Path("."),
):
    '''
    Label connected components in a binary segmentation MRC and write a labelled MRC
    '''
    labelFuncs.label_components(input, output)
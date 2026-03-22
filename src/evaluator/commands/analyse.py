'''
=======================================
EValuator: SEGMENTATION ANALYSIS PIPELINE
=======================================
'''
# ====================
# Import dependencies
# ====================
from pathlib import Path
from typing import Annotated
import typer

# ====================
# Import EValuator functions and variables
# ====================
from ..main import config
from .. import utils as evalutil


# ====================
# Initialise typer as evaluatorAnalyse
# ====================
evaluatorAnalyse = typer.Typer(
    # Disable --install-completion and --show-completion options in terminal
    add_completion=False
)

# ====================
# Define command: analyse
# ====================
@evaluatorAnalyse.command(rich_help_panel="Commands")
def analyse(
    # --------------------
    # Define CLI arguments
    # --------------------
    # Define input argument: should be a path which exists and is readable, and can be a file or directory 
    input: Annotated[
        Path | None, 
        typer.Argument(help="Path to either a single .MRC segmentation file or a directory containing multiple .MRC segmentation files.", exists=True,file_okay=True,dir_okay=True,readable=True)
        ],
    # Define output argument: should be a path which can not exist or is a writeable directory if it exists
    output: Annotated[
        Path | None, 
        typer.Argument(help="Path to output directory.", file_okay=False,dir_okay=True,writable=True)
        ] = ".",
    # --------------------
    # Define CLI options
    # --------------------
    # Define mindiam option: should be a float which is greater than 0, and defaults to the 'min_diameter_nm' value specified in config.toml
    mindiam: Annotated[
        float,
        typer.Option("--min-diam", help="Minimum EV equivalent diameter in nm to use for filtering.", min=0)
    ] = config['filter']['min_diameter_nm'],
    # Define maxdiam option: should be a float which is greater than 0, and defaults to the 'max_diameter_nm' value specified in config.toml
    maxdiam: Annotated[
        float,
        typer.Option("--max-diam", help="Maximum EV equivalent diameter in nm to use for filtering.", min=0)
    ] = config['filter']['max_diameter_nm'],
    # Define fillthreshold option: should be a float which is greater than 0, and defaults to the 'closure_fill_threshold' value specified in config.toml
    fillthreshold: Annotated[
        float,
        typer.Option("--fill-threshold", help="Closure fill threshold to use for determining enclosed EVs.", min=0.0, max=1.0)
    ] = config['filter']['closure_fill_threshold'],
):
    # Set help text for 'analyse' command using docstring
    '''
    Run post-processing pipeline on MemBrain-seg EV segmentation files.
    '''
    process_segmentation()
    # FUNCTION: parse_arguments -- NOT NEEDED
    # FUNCTION: validate_input -- NOT NEEDED
    # FUNCTION: validate_ouptut - needs adjustment
    # FUNCTION: validate_args - needs adjustment
    # FUNCTION: morphological closure
    # FUNCTION: read_segmentation_mrc (utils)
    # FUNCTION: label_components (utils)
    # FUNCTION: check enclosed
    # FUNCTION: compute_surface_area
    # FUNCTION: derive_axes
    # FUNCTION: measure_membrane_vol_diameter
    # FUNCTION: create_component_mask
    # FUNCTION: measure_lumen_vol
    # FUNCTION: measure_axes
    # FUNCTION: measure_eccentricity_aspectratio
    # FUNCTION: save_results_csv
    # FUNCTION: process_component
    # FUNCTION: process_segmentation
    print(f"Analyse command started...")

def process_segmentation():
    print("Function: process_segmentation")
    print("Function: process_segmentation in verbose mode") if config['global']['verbose'] == True else None
    print("Function: process_segmentation in debug mode") if config['global']['debug'] == True else None
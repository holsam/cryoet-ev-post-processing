'''
=======================================
EValuator: SEGMENTATION EV LABELLING
=======================================
'''
# ====================
# Import external dependencies
# ====================
import numpy, typer
from concurrent.futures import as_completed, ProcessPoolExecutor
from pathlib import Path
from psutil import virtual_memory
from typing import Annotated

# ====================
# Import EValuator utilities
# ====================
from evaluator.utils.settings import config, lg
from evaluator.utils import mrc as mrcutil
from evaluator.utils import paths as pathutil

# ====================
# Define label_components: main entrypoint for label command
# ====================
def label_components(input, output):
    # Initialise variables
    mrc_files = []
    n_ok, n_fail = 0, 0
    # Validate input files
    lg.debug(f"label | Validating input...")
    if input.is_file():
        if mrcutil.validateMRCFile(input):
            lg.debug(f"label | {input.name} is a valid MRC file.")
            mrc_files.append(input)
        else:
            lg.warning(f"label | {input.name} is not a valid MRC file and will not be processed.")
            lg.error(f"label | {input.name} is not a valid MRC file.")
    elif input.is_dir():
        found_files = input.glob("[!.]^*.mrc", case_sensitive=False)
        for file in found_files:
            if mrcutil.validateMRCFile(file):
                lg.debug(f"label | {file.name} is a valid MRC file.")
                mrc_files.append(file)
            else:
                lg.warning(f"label | {file.name} is not a valid MRC file and will not be processed.")
    else:
        raise ValueError(f"label | {input.name} is not a supported Path type.")
    # Label each file
    workers = _worker_cap()
    worker_args = [(mrc_file, output) for mrc_file in mrc_files]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_label_mrc_components, args) for args in worker_args}
        for future in as_completed(futures):
            worker_result = future.result
            if worker_result:
                n_ok += 1
            else:
                n_fail += 1
    # Print completion message
    lg.info(f"label | Finished labelling {n_ok + n_fail} file(s): {n_ok} file(s) labelled successfully; {n_fail} file(s) labelled unsuccessfully.")


# ====================
# _worker_cap: calculates rough cap on worker numbers based on available memory
# ====================
def _worker_cap() -> int:
    # memory needed per file (GB) - rough estimate
    mem_per_file = 4.0
    # total memory
    total_memory = virtual_memory().total / 1024**3
    # return 
    return int(numpy.floor(total_memory/mem_per_file))

# ====================
# _label_mrc_components: labels components in a single MRC file
# ====================
def _label_mrc_components(
    mrc_file,
    out_dir
) -> bool:
    '''
    Label connected components in a binary segmentation MRC and write a labelled MRC.

    Reads a binary segmentation (e.g. from MemBrain-seg), assigns a unique integer
    label to each connected component using 6-connectivity, and saves the result as
    an MRC file. Returns True/False corresponding to successful completion.
    '''
    try:
        # Read segmentation
        lg.debug(f"label | Reading input segmentation file {mrc_file.name}...")
        seg_data, voxel_size_nm = mrcutil.readMRCFile(mrc_file)
        seg_data = seg_data.astype(bool)
        # Label components
        lg.info(f"label | Labelling connected components...")
        labelled, n_components = mrcutil.labelComponents(seg_data)
        lg.info(f"label | {n_components} components identified.")
        # Build output path
        lg.debug(f"label | Creating output directory structure...")
        out_dir = pathutil.generateOutputFileStructure(out_dir, "label")
        out_file = Path(out_dir, f"{mrc_file.stem}_labelled.mrc")
        # Resolve name conflicts
        if out_file.exists():
            counter = 1
            while True:
                out_file = Path(out_dir, f"{mrc_file.stem}_labelled-{counter}.mrc")
                if not out_file.exists():
                    break
                counter += 1
        # Write labelled MRC
        lg.debug(f"label | Writing labelled MRC to {out_file.name}...")
        mrcutil.writeMRCFile(labelled.astype(numpy.float32), voxel_size_nm, out_file)
        lg.info(f"label | Finished labelling {mrc_file.name}: {n_components}.")
        return True
    except Exception as e:
        lg.warning(f"label | Labelling failed for {mrc_file.name}: {e}")
        return False
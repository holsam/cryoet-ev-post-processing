'''
=======================================
EV SEGMENTATION LABELLING
=======================================
usage: ev-label.py [-h] -t TOMO -s SEG -o OUTPUT [-c CSV] [--slice SLICE] [--n-slices N_SLICES] [--min-diam MIN_DIAM] [--max-diam MAX_DIAM] [--fill-threshold FILL_THRESHOLD] [-v]
---------------------------------------
Description: Labels a cryo-ET tomogram with EV segmentations as analysed using the accompanying pipeline. Components are coloured by label; components discarded by ev-post-processing.py are hidden.
---------------------------------------
TODO: how to use
# Tiled panel (9 slices) using pipeline CSV for filtering
python ev-label.py -t tomo.mrc -s seg.mrc -o output.png -c results.csv

# Tiled panel with 16 slices, no CSV (re-runs filters)
python ev-label.py -t tomo.mrc -s seg.mrc -o output.png --n-slices 16

# Single Z-slice
python ev-label.py -t tomo.mrc -s seg.mrc -o output.png -c results.csv --slice 128
---------------------------------------
NOTE:
    - OVERLAY STYLE
        Change the OVERLAY_STYLE constant below to switch rendering mode:
            - "filled"   : semi-transparent filled regions per component
            - "contours" : outlines/contours only per component
            - "both"     : filled regions + contours (default)
    - COMPONENT FILTERING
        - If a CSV from ev-post-processing.py is supplied via -c/--csv, valid component
        labels are read directly from it (matched by tomogram filename + label number).
        - If no CSV is supplied, or if no matching rows are found in the CSV, the script
        falls back to re-running the same size/extent filters used by ev-post-processing.py
        (controlled by --min-diam, --max-diam, --fill-threshold).
---------------------------------------
LOGGING EXPLANATION
    Default logging state is 'Warning' (30): outputs warnings and core messages.
    -v  sets logging level to 'Info' (20): shows progress of component filtering/rendering.
    -vv sets logging level to 'Debug' (10): shows function-level detail.
---------------------------------------
'''

# =========================
# IMPORT DEPENDENCIES
# =========================
import argparse, logging, matplotlib, mrcfile, numpy, pandas, sys
import matplotlib.pyplot as plt
import matplotlib.patches as mpatch
from pathlib import Path
from scipy import ndimage
from skimage import measure
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
matplotlib.use("Agg")

# =========================
# SET DEFAULT CONFIGURATION
# =========================
OVERLAY_STYLE = "both"    # style of overlay to use (valid options: both, filled, contours)
N_SLICES = 9              # default number of slices in tiled panel
VERBOSITY = 0
# Matplotlib style
COLORMAP = "tab20"        # matplotlib colormap used to assign colours to component labels
ALPHA_FILL = 0.35         # opacity of filled overlay regions
CONTOUR_LINEWIDTH = 1.0   # line width for contour overlays
LABEL_FONTSIZE = 6        # font size for component label text annotations
FIGURE_DPI = 300          # output image resolution in dots per inch
# Filtering default config - TODO: look into putting this in single file to avoid changing both around?
CLOSURE_FILL_THRESHOLD = 0.05
MAX_DIAMETER_NM = 500.0
MIN_DIAMETER_NM = 20.0


# =========================
# INITIALISE LOGGER
# =========================
lg = logging.getLogger("__name__")

# =========================
# DEFINE FUNCTION: parse_arguments
# =========================
def parse_arguments():
    parser = argparse.ArgumentParser(description="Label EV segmentations overlaid on cryo-ET tomograms.")
    parser.add_argument("-t", "--tomo", type=Path, required=True, help="Path to the original (unsegmented) tomogram .mrc file")
    parser.add_argument("-s", "--seg", type=Path, required=True, help="Path to the segmented .mrc file (membrain-seg output)")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Path to output image file (e.g. output.png or output.jpg)")
    parser.add_argument("-c", "--csv", type=Path, default=None, help="Path to ev-post-processing.py output CSV (used to identify valid EV components). If omitted, falls back to re-running size/extent filters.")
    parser.add_argument("--slice", type=int, default=None, help="Render a single Z-slice at this index instead of a tiled panel")
    parser.add_argument("--n-slices", type=int, default=N_SLICES, help=f"Number of evenly-spaced slices in the tiled panel (default: {N_SLICES})")
    parser.add_argument("--min-diam", type=float, default=MIN_DIAMETER_NM, help=f"Fallback filter: minimum equivalent diameter in nm (default: {MIN_DIAMETER_NM})")
    parser.add_argument("--max-diam", type=float, default=MAX_DIAMETER_NM, help=f"Fallback filter: maximum equivalent diameter in nm (default: {MAX_DIAMETER_NM})")
    parser.add_argument("--fill-threshold", type=float, default=CLOSURE_FILL_THRESHOLD, help=f"Fallback filter: closure fill threshold (default: {CLOSURE_FILL_THRESHOLD})")
    parser.add_argument("-v", "--verbosity", action="count", default=VERBOSITY, help="Increase verbosity (-v: info messages; -vv: debug messages)")
    return parser.parse_args()

# =========================
# DEFINE FUNCTION: read_mrc
# =========================
def read_mrc(path: Path):
    '''
    Read an MRC file and return the data array and voxel size in nm.
    Returns voxel_size_nm=None if no voxel size is encoded in the header.
    '''
    with mrcfile.open(str(path), mode="r", permissive=True) as file:
        data = file.data.copy()
        vox_a = float(file.voxel_size.x)
    if vox_a == 0.0:
        lg.warning(f"{path.name}: voxel size not found in MRC header. Physical measurement units will be voxels - set voxel size manually.")
        voxel_size_nm = None
    else:
        # Convert Å to nm
        voxel_size_nm = vox_a / 10.0
    return data, voxel_size_nm

# =========================
# DEFINE FUNCTION: label_components
# =========================
def label_components(binary_vol: numpy.ndarray):
    '''
    Labels connected components in binary volumes using full 3D (26) connectivity 
    '''
    struc = ndimage.generate_binary_structure(3, 3)
    components, n_components = ndimage.label(binary_vol, structure=struc)
    return components, n_components

# =========================
# DEFINE FUNCTION: get_valid_labels_from_csv
# =========================
def get_valid_labels_from_csv(csv_path: Path, seg_filename: str):
    '''
    Reads the ev-post-processing.py output CSV and returns the set of integer component
    labels that passed the pipeline for the given segmentation filename.

    Returns None if:
      - the CSV cannot be read, or
      - no rows match the given segmentation filename (triggering the filter fallback).
    '''
    try:
        df = pandas.read_csv(csv_path)
    except Exception as e:
        lg.warning(f"Could not read CSV '{csv_path}': {e}. Falling back to filter-based approach.")
        return None
    if "tomogram" not in df.columns or "label" not in df.columns:
        lg.warning(f"CSV '{csv_path}' is missing 'tomogram' or 'label' columns. Falling back to filter-based approach.")
        return None
    matching = df[df["tomogram"] == seg_filename]
    if matching.empty:
        lg.warning(f"No entries for '{seg_filename}' in CSV.\nCheck the 'tomogram' column contains exact filenames.\nRe-filtering segmented tomogram.")
        return None
    valid_labels = set(matching["label"].astype(int).tolist())
    lg.info(f"Loaded {len(valid_labels)} valid component labels from CSV for '{seg_filename}'.")
    return valid_labels

# =========================
# DEFINE FUNCTION: get_valid_labels_from_filters
# =========================
def get_valid_labels_from_filters(labelled_vol, voxel_size_nm, min_diam, max_diam):
    '''
    Re-applies the size and extent filters from ev-post-processing.py to identify
    valid component labels. Used as a fallback when no CSV is available.

    Replicates the min/max voxel count (derived from min/max diameter) and
    extent (>0.01) pre-filters used in process_segmentation().
    '''
    if voxel_size_nm is not None:
        min_vox = (min_diam / (2 * voxel_size_nm)) ** 3 * (4/3) * numpy.pi
        max_vox = (max_diam / (2 * voxel_size_nm)) ** 3 * (4/3) * numpy.pi
    else:
        lg.warning("Voxel size unknown; skipping diameter-based size filter.")
        min_vox, max_vox = 0, numpy.inf
    component_list = measure.regionprops(labelled_vol)
    valid_labels = set()
    for component in component_list:
        if not (min_vox <= component.area <= max_vox):
            continue
        if component.extent < 0.01:
            continue
        valid_labels.add(component.label)
    lg.info(f"Filter-based approach identified {len(valid_labels)} valid components.")
    return valid_labels

# =========================
# DEFINE FUNCTION: assign_label_colours
# =========================
def assign_label_colours(valid_labels: set) -> dict:
    '''
    Assigns a unique RGBA colour to each valid label using COLORMAP.
    Colours cycle through the colormap if there are more labels than colours.
    Returns a dict mapping label (int) -> RGBA tuple.
    '''
    cmap = plt.get_cmap(COLORMAP)
    n_colours = cmap.N if hasattr(cmap, "N") else 256
    sorted_labels = sorted(valid_labels)
    return {label: cmap(i % n_colours) for i, label in enumerate(sorted_labels)}

# =========================
# DEFINE FUNCTION: get_label_centroid_2d
# =========================
def get_label_centroid_2d(seg_slice: numpy.ndarray, label: int):
    '''
    Returns the (row, col) centroid of a given label within a 2D segmentation slice.
    Returns None if the label is absent from this slice.
    '''
    mask = seg_slice == label
    if not numpy.any(mask):
        return None
    rows, cols = numpy.where(mask)
    return int(rows.mean()), int(cols.mean())

# =========================
# DEFINE FUNCTION: overlay_filled
# =========================
def overlay_filled(ax, seg_slice: numpy.ndarray, valid_labels: set, label_colours: dict):
    '''
    Overlays semi-transparent filled regions for each valid label.

    To use this style exclusively: set OVERLAY_STYLE = "filled" at the top of this script.
    '''
    # Build an RGBA overlay array and fill each label's pixels
    overlay = numpy.zeros((*seg_slice.shape, 4), dtype=float)
    for label in valid_labels:
        mask = seg_slice == label
        if not numpy.any(mask):
            continue
        colour = label_colours[label]
        overlay[mask, 0] = colour[0]
        overlay[mask, 1] = colour[1]
        overlay[mask, 2] = colour[2]
        overlay[mask, 3] = ALPHA_FILL
    ax.imshow(overlay, interpolation="nearest")
    # Annotate each visible label with its number at the centroid
    for label in valid_labels:
        centroid = get_label_centroid_2d(seg_slice, label)
        if centroid is not None:
            ax.text(centroid[1], centroid[0], str(label), color="white", fontsize=LABEL_FONTSIZE, ha="center", va="center", fontweight="bold")

# =========================
# DEFINE FUNCTION: overlay_contours
# =========================
def overlay_contours(ax, seg_slice: numpy.ndarray, valid_labels: set, label_colours: dict):
    '''
    Overlays contour outlines for each valid label using skimage.measure.find_contours.

    To use this style exclusively: set OVERLAY_STYLE = "contours" at the top of this script.
    '''
    for label in valid_labels:
        mask = (seg_slice == label).astype(numpy.uint8)
        if not numpy.any(mask):
            continue
        colour = label_colours[label]
        contours = measure.find_contours(mask, level=0.5)
        for contour in contours:
            ax.plot(contour[:, 1], contour[:, 0], color=colour, linewidth=CONTOUR_LINEWIDTH, alpha=0.9)
        # Annotate each visible label at its centroid
        centroid = get_label_centroid_2d(seg_slice, label)
        if centroid is not None:
            ax.text(centroid[1], centroid[0], str(label),color=colour, fontsize=LABEL_FONTSIZE,ha="center", va="center", fontweight="bold")

# =========================
# DEFINE FUNCTION: overlay_both
# =========================
def overlay_both(ax, seg_slice: numpy.ndarray, valid_labels: set, label_colours: dict):
    '''
    Overlays both semi-transparent filled regions and contour outlines (default style).

    To use this style: set OVERLAY_STYLE = "both" at the top of this script.
    Calls overlay_filled then overlay_contours, so annotations appear on top of fills.
    '''
    overlay_filled(ax, seg_slice, valid_labels, label_colours)
    overlay_contours(ax, seg_slice, valid_labels, label_colours)

# =========================
# DEFINE FUNCTION: select_overlay_fn
# =========================
def select_overlay_fn():
    '''
    Returns the appropriate overlay rendering function based on OVERLAY_STYLE.
    Falls back to overlay_both with a warning if OVERLAY_STYLE is unrecognised.
    '''
    options = {"filled":   overlay_filled, "contours": overlay_contours, "both":     overlay_both}
    fn = options.get(OVERLAY_STYLE)
    if fn is None:
        lg.warning(f"Unrecognised OVERLAY_STYLE '{OVERLAY_STYLE}'. Defaulting to 'both'.")
        return overlay_both
    return fn

# =========================
# DEFINE FUNCTION: normalise_slice
# =========================
def normalise_slice(s: numpy.ndarray) -> numpy.ndarray:
    '''
    Normalises a 2D array to [0.0, 1.0] for greyscale display.
    Returns a zero array if the slice is constant to avoiding division by zero error.
    '''
    s = s.astype(float)
    mn, mx = s.min(), s.max()
    if mx > mn:
        return (s - mn) / (mx - mn)
    return numpy.zeros_like(s)

# =========================
# DEFINE FUNCTION: build_legend_patches
# =========================
def build_legend_patches(valid_labels: set, label_colours: dict) -> list:
    '''
    Builds a list of matplotlib Patch objects for use in a figure legend,
    one per valid EV label.
    '''
    return [mpatch.Patch(color=label_colours[l], label=f"EV {l}") for l in sorted(valid_labels)]

# =========================
# DEFINE FUNCTION: render_tiled
# =========================
def render_tiled(tomo_data, seg_labelled, valid_labels, label_colours, n_slices, overlay_fn, output_path: Path, seg_name: str):
    '''
    Renders a tiled panel of evenly-spaced Z-slices with segmentation overlay.

    Slices are selected by numpy.linspace across the full Z range, so the panel
    gives an overview of the whole tomogram. Each tile shows:
      - greyscale tomogram slice as background
      - EV overlay (style controlled by OVERLAY_STYLE)
      - Z-index label in the top-left corner
    A shared legend is placed below the panel.
    '''
    n_z = tomo_data.shape[0]
    slice_indices = numpy.linspace(0, n_z - 1, n_slices, dtype=int)
    # Arrange tiles in a roughly square grid
    n_cols = int(numpy.ceil(numpy.sqrt(n_slices)))
    n_rows = int(numpy.ceil(n_slices / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(3 * n_cols, 3 * n_rows), facecolor="black")
    axes = numpy.array(axes).flatten()
    for i, z in enumerate(slice_indices):
        ax = axes[i]
        ax.set_facecolor("black")
        tomo_slice = normalise_slice(tomo_data[z])
        seg_slice = seg_labelled[z]
        ax.imshow(tomo_slice, cmap="gray", interpolation="nearest", vmin=0, vmax=1)
        overlay_fn(ax, seg_slice, valid_labels, label_colours)
        ax.text(4, 4, f"z={z}", color="yellow", fontsize=6, va="top", ha="left")
        ax.axis("off")
    # Hide any unused subplot axes
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")
        axes[j].set_facecolor("black")
    # Shared legend below the panel
    patches = build_legend_patches(valid_labels, label_colours)
    if patches:
        fig.legend(handles=patches, loc="lower center", ncol=min(len(patches), 10), fontsize=6, framealpha=0.5, facecolor="black", labelcolor="white", bbox_to_anchor=(0.5, -0.02))
    fig.suptitle(seg_name, color="white", fontsize=9, y=1.005)
    plt.tight_layout(pad=0.3)
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    lg.info(f"Tiled panel ({n_slices} slices) saved to {output_path}")

# =========================
# DEFINE FUNCTION: render_single_slice
# =========================
def render_single_slice(tomo_data, seg_labelled, valid_labels, label_colours,slice_idx: int, overlay_fn, output_path: Path, seg_name: str):
    '''
    Renders a single Z-slice with segmentation overlay.
    Use --slice <index> at the command line to invoke this mode.
    '''
    n_z = tomo_data.shape[0]
    if not (0 <= slice_idx < n_z):
        raise ValueError(f"Slice index {slice_idx} is out of range for tomogram with {n_z} Z-slices (0–{n_z - 1}).")
    fig, ax = plt.subplots(1, 1, figsize=(8, 8), facecolor="black")
    ax.set_facecolor("black")
    tomo_slice = normalise_slice(tomo_data[slice_idx])
    seg_slice = seg_labelled[slice_idx]
    ax.imshow(tomo_slice, cmap="gray", interpolation="nearest", vmin=0, vmax=1)
    overlay_fn(ax, seg_slice, valid_labels, label_colours)
    ax.text(4, 4, f"z={slice_idx}", color="yellow", fontsize=8, va="top", ha="left")
    ax.axis("off")
    patches = build_legend_patches(valid_labels, label_colours)
    if patches:
        ax.legend(handles=patches, loc="lower right", fontsize=7, framealpha=0.5, facecolor="black", labelcolor="white")
    ax.set_title(f"{seg_name}  |  z={slice_idx}", color="white", fontsize=9)
    plt.tight_layout(pad=0.3)
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    lg.info(f"Single-slice image (z={slice_idx}) saved to {output_path}")

# =========================
# DEFINE FUNCTION: main
# =========================
def main():
    global OVERLAY_STYLE, N_SLICES, MIN_DIAMETER_NM, MAX_DIAMETER_NM, CLOSURE_FILL_THRESHOLD
    # ---------------------
    # Print startup message
    # ---------------------
    print(f"\nEV SEGMENTATION LABELLING")
    print(f"Full command: {' '.join(sys.argv)}")
    # ---------------------
    # Parse arguments and set defaults for non-defined variables
    # ---------------------
    args = parse_arguments()
    verbosity_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    VERBOSITY = verbosity_levels[min(args.verbosity, len(verbosity_levels) - 1)]
    MIN_DIAMETER_NM = args.min_diam
    MAX_DIAMETER_NM = args.max_diam
    CLOSURE_FILL_THRESHOLD = args.fill_threshold
    N_SLICES = args.n_slices
    # ---------------------
    # Set up logger configuration
    # ---------------------
    logging.basicConfig(format="%(asctime)s %(levelname)-10s %(message)s",datefmt="%Y-%m-%d %H:%M:%S", level = VERBOSITY)
    # ---------------------
    # Validate input files
    # ---------------------
    for p in [args.tomo, args.seg]:
        if not p.exists():
            raise FileNotFoundError(f"{p} does not exist.")
        if p.suffix.lower() != ".mrc":
            raise ValueError(f"{p} does not appear to be an MRC file.")
    if args.csv is not None and not args.csv.exists():
        raise FileNotFoundError(f"CSV file {args.csv} does not exist.")
    # ---------------------
    # Read MRC files
    # ---------------------
    lg.info(f"Reading tomogram: {args.tomo}")
    tomo_data, _ = read_mrc(args.tomo)
    lg.info(f"Reading segmentation: {args.seg}")
    seg_data, voxel_size_nm = read_mrc(args.seg)
    if voxel_size_nm is None:
        lg.warning("Voxel size not found in segmentation header. Diameter-based fallback filter will be skipped.")
    if tomo_data.shape != seg_data.shape:
        raise ValueError(f"Tomogram shape {tomo_data.shape} and segmentation shape {seg_data.shape} do not match.\nCheck that both files correspond to the same tomogram.")
    # ---------------------
    # Label connected components
    # ---------------------
    lg.info("Labelling connected components...")
    seg_labelled, n_components = label_components(seg_data.astype(bool))
    lg.info(f"{n_components} total components found in segmentation.")
    # ---------------------
    # Determine valid labels
    # ---------------------
    valid_labels = None
    if args.csv is not None:
        valid_labels = get_valid_labels_from_csv(args.csv, args.seg.name)
    if valid_labels is None:
        lg.info("Using filter-based fallback to identify valid components.")
        valid_labels = get_valid_labels_from_filters(seg_labelled, voxel_size_nm, MIN_DIAMETER_NM, MAX_DIAMETER_NM)
    if not valid_labels:
        lg.warning("No valid EV components identified. Output will show only the tomogram.")
    print(f"{len(valid_labels)} EV components will be overlaid.")
    # ---------------------
    # Assign colours and select overlay function
    # ---------------------
    label_colours = assign_label_colours(valid_labels)
    overlay_fn = select_overlay_fn()
    lg.info(f"Overlay style: '{OVERLAY_STYLE}'")
    # ---------------------
    # Ensure output directory exists
    # ---------------------
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # ---------------------
    # Render image and save
    # ---------------------
    if args.slice is not None:
        render_single_slice(tomo_data, seg_labelled, valid_labels, label_colours, args.slice, overlay_fn, args.output, args.seg.name)
    else:
        render_tiled(tomo_data, seg_labelled, valid_labels, label_colours, N_SLICES, overlay_fn, args.output, args.seg.name)
    print(f"\Labelled tomogram saved to: {args.output}")

if __name__ == "__main__":
    main()
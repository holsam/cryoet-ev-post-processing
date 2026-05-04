# -- Import external dependencies ------
import mrcfile, os, sys, typer
import numpy as np
from pathlib import Path
from scipy.ndimage import gaussian_filter
from typing import Annotated

# -- Define output paths ---------------
OUT_DIR   = Path(__file__).parent
TOMO_PATH = OUT_DIR / "test_tomogram.mrc"
SEG_PATH  = OUT_DIR / "test_segmentation.mrc"

# -- Define volume parameters ----------
Z, Y, X = 300, 682, 960
VOX_A = 5.36
VOX_NM = VOX_A / 10.0

# -- Define EV placement parameters ----
SHELL_THICKNESS_VOX = 10 # ~5.4 nm - representative MemBrain-seg bilayer depth
R_OUTER_MIN = 40 # ~42.9 nm outer diameter - small exosome scale
R_OUTER_MAX = 120 # ~128.6 nm outer diameter - upper end of small EV range
EDGE_PADDING = 20 # min voxels between EV surface and volume boundary
MAX_ATTEMPTS = 5000 # placement attempts per EV before aborting

# -- Define generate_ev_defs function --
def generate_ev_defs(n_evs, rng, shape):
    """
    Randomly generate n_evs EV definitions within the given volume.

    For each EV, a random outer radius is drawn uniformly from
    [R_OUTER_MIN, R_OUTER_MAX]. The centre is then drawn uniformly from the
    interior region that keeps the entire shell at least EDGE_PADDING voxels
    from any face of the volume. Two separation constraints are enforced:

      1. No shell overlap: centre-to-centre distance must exceed
         r_outer_a + r_outer_b (shells do not intersect).
      2. One-shell-width gap: the minimum separation is increased by a further
         SHELL_THICKNESS_VOX voxels, ensuring the shells are separated by a gap.
         This guarantees they remain distinct connected components after
         26-connectivity labelling.
    """
    zv, yv, xv = shape
    placed = []
    for i in range(n_evs):
        for attempt in range(MAX_ATTEMPTS):
            r_outer = int(rng.integers(R_OUTER_MIN, R_OUTER_MAX + 1))
            r_inner = r_outer - SHELL_THICKNESS_VOX
            margin = r_outer + EDGE_PADDING
            if 2 * margin >= min(zv, yv, xv):
                raise RuntimeError(
                    f"Volume {shape} is too small to fit EVs with r_outer up to "
                    f"{r_outer} vox and EDGE_PADDING={EDGE_PADDING}."
                )
            cz = int(rng.integers(margin, zv - margin))
            cy = int(rng.integers(margin, yv - margin))
            cx = int(rng.integers(margin, xv - margin))
            # Check separation from all previously placed EVs
            ok = True
            for prev in placed:
                pz, py, px = prev["centre"]
                dist    = np.sqrt((cz-pz)**2 + (cy-py)**2 + (cx-px)**2)
                min_sep = r_outer + prev["r_outer"] + SHELL_THICKNESS_VOX
                if dist < min_sep:
                    ok = False
                    break
            if ok:
                placed.append({
                    "centre":  (cz, cy, cx),
                    "r_outer": r_outer,
                    "r_inner": r_inner,
                })
                diam_nm = r_outer * 2 * VOX_NM
                print(
                    f"  EV {i+1:>2d}:  centre=({cz:>3d}, {cy:>3d}, {cx:>3d})  "
                    f"r_outer={r_outer:>3d} vox  "
                    f"outer diam ~{diam_nm:.1f} nm  "
                    f"[attempt {attempt+1}]"
                )
                break
        else:
            raise RuntimeError(
                f"Could not place EV {i+1} after {MAX_ATTEMPTS} attempts. "
                f"The volume may be too crowded for {n_evs} EVs at the current "
                f"size range. Try reducing --n-evs."
            )
    return placed

# -- Define build_coordinate_grid function
def build_coordinate_grid(shape):
    """
    Return open (sparse) ZYX coordinate arrays for the given shape.

    Using open grids rather than dense np.mgrid significantly reduces peak
    memory during construction whilst broadcasting correctly in distance
    calculations.
    """
    zv, yv, xv = shape
    zz = np.arange(zv, dtype=np.float32).reshape(-1, 1, 1)
    yy = np.arange(yv, dtype=np.float32).reshape(1, -1, 1)
    xx = np.arange(xv, dtype=np.float32).reshape(1, 1, -1)
    return zz, yy, xx

# -- Define build_segmentation function
def build_segmentation(shape, ev_defs):
    """
    Build a binary float32 membrane segmentation mask.

    Each EV is a hollow spherical shell: voxels with
    r_inner <= distance_from_centre <= r_outer are set to 1.0, all others 0.0.
    This format matches the binary masks produced by MemBrain-seg.
    """
    zv, yv, xv = shape
    seg = np.zeros((zv, yv, xv), dtype=np.float32)
    zz, yy, xx = build_coordinate_grid(shape)
    for ev in ev_defs:
        cz, cy, cx = ev["centre"]
        r_o, r_i   = ev["r_outer"], ev["r_inner"]
        dist  = np.sqrt((zz - cz)**2 + (yy - cy)**2 + (xx - cx)**2)
        shell = (dist >= r_i) & (dist <= r_o)
        seg[shell] = 1.0
    return seg

# -- Define build_tomogram function ----
def build_tomogram(shape, ev_defs, rng):
    """
    Build a float32 greyscale cryo-ET-like volume.
    """
    zv, yv, xv = shape
    zz, yy, xx = build_coordinate_grid(shape)

    print("  Generating background noise...")
    tomo = rng.standard_normal((zv, yv, xv)).astype(np.float32)
    tomo = gaussian_filter(tomo, sigma=1.2).astype(np.float32)

    # Low-frequency YX intensity gradient
    grad_y = np.linspace(-0.15, 0.15, yv, dtype=np.float32)
    grad_x = np.linspace(-0.10, 0.10, xv, dtype=np.float32)
    tomo  += np.outer(grad_y, grad_x)[np.newaxis, :, :]

    print("  Adding EV contrast...")
    for ev in ev_defs:
        cz, cy, cx = ev["centre"]
        r_o, r_i   = ev["r_outer"], ev["r_inner"]
        dist = np.sqrt((zz - cz)**2 + (yy - cy)**2 + (xx - cx)**2)
        tomo[(dist >= r_i) & (dist <= r_o)] += 1.8   # bright membrane
        tomo[dist < r_i]                    -= 0.3   # attenuated lumen

    print("  Applying PSF smoothing...")
    tomo = gaussian_filter(tomo, sigma=0.5).astype(np.float32)
    return tomo

# -- Define write_mrc function ---------
def write_mrc(data, path, voxel_size_a):
    """Write a float32 array to an MRC2014 file with the given voxel size (Angstrom)."""
    with mrcfile.new(str(path), overwrite=True) as mrc:
        mrc.set_data(data)
        mrc.voxel_size = voxel_size_a

# -- Define Typer class for script -----
evaluatorTestDataGenerator = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# -- Define command/arguments for script
@evaluatorTestDataGenerator.command()
def main(
    n_evs: Annotated[
        int,
        typer.Option('-N','--n-evs',help='Number of EVs to place in the test files')
    ] = 4,
    seed: Annotated[
        int,
        typer.Option('--seed', help='Random seed for reproducible EV placement')
    ] = 42,
):
    '''
    Generate synthetic MRC test files for the EValuator test suite
    '''
    rng = np.random.default_rng(seed)
    shape = (Z, Y, X)
    size_mb = (Z * Y * X * 4) / (1024**2)
    print(f"\nEValuator test data generator")
    print(f"─────────────────────────────────────────────────────")
    print(f"  Volume shape   : {shape}  (Z x Y x X)")
    print(f"  Aspect ratio   : 1 : {Y/Z:.3f} : {X/Z:.3f}")
    print(f"  Voxel size     : {VOX_A} A  ({VOX_NM:.3f} nm/vox)")
    print(f"  File size      : ~{size_mb:.0f} MB per file  (~{2*size_mb/1024:.2f} GB total)")
    print(f"  EVs to place   : {n_evs}")
    print(f"  Shell thickness: {SHELL_THICKNESS_VOX} vox  ({SHELL_THICKNESS_VOX * VOX_NM:.1f} nm)")
    print(f"  EV diam. range : {R_OUTER_MIN*2*VOX_NM:.0f}-{R_OUTER_MAX*2*VOX_NM:.0f} nm")
    print(f"─────────────────────────────────────────────────────\n")
    # Place EVs
    print("Placing EVs...")
    try:
        ev_defs = generate_ev_defs(n_evs, rng, shape)
    except RuntimeError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    # Build and write segmentation first
    print("\nBuilding segmentation mask...")
    seg = build_segmentation(shape, ev_defs)
    print(f"  Membrane voxels: {int(seg.sum()):,}")
    print(f"Writing {SEG_PATH.name}...")
    write_mrc(seg, SEG_PATH, VOX_A)
    del seg
    # Build and write tomogram
    print("\nBuilding tomogram...")
    tomo = build_tomogram(shape, ev_defs, rng)
    print(f"Writing {TOMO_PATH.name}...")
    write_mrc(tomo, TOMO_PATH, VOX_A)
    del tomo
    # Validate outputs
    print("\nValidating output files...")
    all_valid  = True
    total_bytes = 0
    for path in (TOMO_PATH, SEG_PATH):
        size_mb_out  = os.path.getsize(path) / (1024**2)
        total_bytes += os.path.getsize(path)
        valid        = mrcfile.validate(str(path), print_file=None)
        status       = "OK" if valid else "INVALID"
        print(f"  [{status}]  {path.name}  ({size_mb_out:.0f} MB)")
        if not valid:
            all_valid = False
    # Print information message
    print(f"\n  Combined size  : {total_bytes / (1024**3):.2f} GB")
    print(f"  Output dir     : {OUT_DIR}\n")
    # Print warning if at least one file fails validation
    if not all_valid:
        print("Warning: one or more output files did not validate.", file=sys.stderr)
        sys.exit(1)
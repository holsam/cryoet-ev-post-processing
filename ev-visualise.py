'''
=======================================
EV VISUALISATION AUXILIARY SCRIPT
=======================================
usage: ev_visualise.py [-h] -i INPUT [-o OUTPUT] [--fps FPS] [--downsample DOWNSAMPLE] [--no-movie] [--no-iso] [-v]
---------------------------------------
Given an MRC file (either a raw tomogram or a segmented mask), generates:
  1. A Z-stack movie (XY constant, Z as time) saved as MP4 or GIF
  2. An isometric view:
       - Mask volumes: 3D surface render (marching cubes) with 0s invisible
       - Greyscale volumes: max intensity projection from isometric angle
---------------------------------------
LOGGING EXPLANATION
    - Default logging state is 'Warning' (30): warnings and core output only
    - -v  sets logging level to 'Info'  (20): progress messages included
    - -vv sets logging level to 'Debug' (10): function-level messages included
---------------------------------------
'''

# =========================
# IMPORT DEPENDENCIES
# =========================
import argparse, logging, matplotlib, mrcfile, numpy, os, sys
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from pathlib import Path
from scipy import ndimage
from skimage import measure
matplotlib.use("Agg")

# =========================
# SET DEFAULT CONFIGURATION
# =========================
DEFAULT_FPS         = 45
DEFAULT_DOWNSAMPLE  = 2
VERBOSITY           = 0

# =========================
# INITIALISE LOGGER
# =========================
lg = logging.getLogger("__name__")

# =========================
# DEFINE FUNCTION: parse_arguments
# =========================
def parse_arguments():
    '''
    Initialise parser, read arguments, and return.
    '''
    parser = argparse.ArgumentParser(description="Auxiliary visualisation script for EV MRC files.")
    parser.add_argument("-i", "--input", type=Path, required=True, help="Path to a single MRC file (raw tomogram or segmented mask)")
    parser.add_argument("-o", "--output", type=Path, default=Path("."), help="Path to output directory (default: current directory)")
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS, help=f"Frame rate for Z-stack movie (default: {DEFAULT_FPS})")
    parser.add_argument("--downsample", type=int, default=DEFAULT_DOWNSAMPLE, help=f"Downsampling factor for isometric render (default: {DEFAULT_DOWNSAMPLE}; 1 = no downsampling)")
    parser.add_argument("--no-movie", action="store_true", help="Skip Z-stack movie generation")
    parser.add_argument("--no-iso", action="store_true", help="Skip isometric view generation")
    parser.add_argument("-v", "--verbosity", action="count", default=VERBOSITY, help="Increase verbosity (-v: info messages; -vv: debug messages)")
    return parser.parse_args()


# =========================
# DEFINE FUNCTION: validate_input
# =========================
def validate_input(args):
    '''
    Confirm that the input path exists and points to an MRC file.
    '''
    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")
    if args.input.suffix.lower() != ".mrc":
        raise ValueError(f"Input file must be an MRC file, got: {args.input.suffix}")
    return args.input


# =========================
# DEFINE FUNCTION: validate_output
# =========================
def validate_output(args):
    '''
    Confirm or create the output directory.
    '''
    if args.output.suffix != "":
        raise ValueError(f"Output must be a directory, not a file: {args.output}")
    if not args.output.exists():
        os.makedirs(args.output)
        lg.info(f"Created output directory: {args.output}")
    elif args.output.is_file():
        raise ValueError(f"Output path is a file, not a directory: {args.output}")
    return args.output


# =========================
# DEFINE FUNCTION: read_mrc
# =========================
def read_mrc(path: Path):
    '''
    Read an MRC file and return the data array and voxel size in nm.
    Voxel size falls back to None if not present in the header.
    '''
    with mrcfile.open(str(path), mode="r", permissive=True) as f:
        data = f.data.copy()
        vox_a = float(f.voxel_size.x)
    voxel_size_nm = (vox_a / 10.0) if vox_a != 0.0 else None
    if voxel_size_nm is None:
        lg.warning(f"{path.name}: voxel size not found in MRC header. Axis labels will be in voxels.")
    lg.info(f"{path.name}: data shape {data.shape}, dtype {data.dtype}, voxel size {voxel_size_nm} nm")
    return data, voxel_size_nm


# =========================
# DEFINE FUNCTION: detect_mask
# =========================
def detect_mask(data: numpy.ndarray) -> bool:
    '''
    Heuristically determine whether the data is a binary segmentation mask.
    A volume is treated as a mask if it contains only two unique values (e.g. 0 and 1).
    '''
    unique_vals = numpy.unique(data)
    is_mask = len(unique_vals) <= 2
    lg.info(f"Volume type detected: {'mask' if is_mask else 'greyscale'} (unique values: {unique_vals[:10]})")
    return is_mask


# =========================
# DEFINE FUNCTION: normalise_greyscale
# =========================
def normalise_greyscale(data: numpy.ndarray) -> numpy.ndarray:
    '''
    Linearly normalise a greyscale volume to [0, 1] for display.
    Clips to the 1st–99th percentile range to avoid outlier-driven contrast collapse.
    '''
    lo = numpy.percentile(data, 1)
    hi = numpy.percentile(data, 99)
    if hi == lo:
        return numpy.zeros_like(data, dtype=numpy.float32)
    return numpy.clip((data.astype(numpy.float32) - lo) / (hi - lo), 0.0, 1.0)


# =========================
# DEFINE FUNCTION: make_movie
# =========================
def make_movie(data: numpy.ndarray, output_path: Path, fps: float, is_mask: bool, voxel_size_nm):
    '''
    Generate a Z-stack movie where each frame is one XY slice, with Z advancing as time.
    Saved as MP4 if FFMpeg is available, otherwise falls back to GIF.
    Args:
        data:           3D numpy array (Z, Y, X)
        output_path:    output directory
        fps:            frames per second
        is_mask:        whether the volume is a binary mask
        voxel_size_nm:  voxel size in nm (or None)
    '''
    lg.info("Generating Z-stack movie...")
    n_z = data.shape[0]
    scale_label = "nm" if voxel_size_nm is not None else "vox"
    if is_mask:
        display = data.astype(numpy.float32)
        cmap = "binary_r"
        vmin, vmax = 0.0, 1.0
    else:
        display = normalise_greyscale(data)
        cmap = "gray"
        vmin, vmax = 0.0, 1.0
    fig, ax = plt.subplots(figsize=(6, 6))
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")
    ax.axis("off")
    im = ax.imshow(display[0], cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest", origin="upper")
    z_label_val = (0 * voxel_size_nm) if voxel_size_nm is not None else 0
    title = ax.set_title(f"Z = {z_label_val:.1f} {scale_label}  (slice 1 / {n_z})", color="white", fontsize=9, pad=4)
    def update(frame_idx):
        im.set_data(display[frame_idx])
        z_val = (frame_idx * voxel_size_nm) if voxel_size_nm is not None else frame_idx
        title.set_text(f"Z = {z_val:.1f} {scale_label}  (slice {frame_idx + 1} / {n_z})")
        return im, title
    anim = animation.FuncAnimation(fig, update, frames=n_z, interval=1000.0/fps, blit=True)
    # Attempt MP4, fall back to GIF
    mp4_path = output_path / "zstack_movie.mp4"
    gif_path = output_path / "zstack_movie.gif"
    writers = animation.writers.list()
    if "ffmpeg" in writers:
        try:
            writer = animation.FFMpegWriter(fps=fps, metadata={"title": "Z-stack movie"}, bitrate=1800)
            anim.save(str(mp4_path), writer=writer, dpi=150)
            lg.info(f"Movie saved (MP4): {mp4_path}")
            print(f"  Z-stack movie saved: {mp4_path}")
        except Exception as e:
            lg.warning(f"FFMpeg write failed ({e}), falling back to GIF.")
            _save_gif(anim, gif_path, fps)
    else:
        lg.warning("FFMpeg not available. Falling back to GIF.")
        _save_gif(anim, gif_path, fps)

    plt.close(fig)


# =========================
# DEFINE FUNCTION: _save_gif (internal helper)
# =========================
def _save_gif(anim, gif_path: Path, fps: float):
    '''
    Save an animation as a GIF using Pillow.
    '''
    try:
        writer = animation.PillowWriter(fps=fps)
        anim.save(str(gif_path), writer=writer, dpi=100)
        lg.info(f"Movie saved (GIF): {gif_path}")
        print(f"  Z-stack movie saved (GIF fallback): {gif_path}")
    except Exception as e:
        lg.error(f"GIF save also failed: {e}")
        print(f"  ERROR: Could not save Z-stack movie. {e}")


# =========================
# DEFINE FUNCTION: _rotate_isometric
# =========================
def _rotate_isometric(vol: numpy.ndarray) -> numpy.ndarray:
    '''
    Rotate a 3D volume to produce an isometric viewing angle.
    Applies a 45° azimuthal rotation (around Z) followed by a 35.264° elevation
    tilt (around the new Y axis) — the standard isometric projection angles.
    Uses linear interpolation (order=1) for speed; mask volumes should be pre-cast
    to float before calling this and thresholded afterwards if needed.
    '''
    # Rotate 45° in the YX plane (around Z axis)
    vol = ndimage.rotate(vol, 45.0, axes=(1, 2), reshape=True, order=1, cval=0.0)
    # Tilt by arctan(1/sqrt(2)) ≈ 35.264° in the ZX plane (around Y axis)
    vol = ndimage.rotate(vol, 35.264, axes=(0, 2), reshape=True, order=1, cval=0.0)
    return vol


# =========================
# DEFINE FUNCTION: make_isometric_mask
# =========================
def make_isometric_mask(data: numpy.ndarray, output_path: Path, downsample: int, voxel_size_nm):
    '''
    For a binary segmentation mask, render an isometric 3D surface view using
    marching cubes. Voxels with value 0 are fully invisible; only the membrane
    surface is shown. The view is set to the standard isometric camera angle.

    Args:
        data:           3D boolean/integer numpy array (Z, Y, X)
        output_path:    output directory
        downsample:     integer downsampling factor (applied before marching cubes)
        voxel_size_nm:  voxel size in nm (or None)
    '''
    lg.info("Generating isometric mask render...")
    vol = data.astype(numpy.uint8)
    if downsample > 1:
        vol = vol[::downsample, ::downsample, ::downsample]
        lg.info(f"Downsampled to {vol.shape} (factor {downsample})")
    if vol.sum() == 0:
        lg.warning("Mask is entirely zero after downsampling — skipping isometric render.")
        print("  WARNING: No foreground voxels found; isometric render skipped.")
        return
    spacing = (voxel_size_nm * downsample,) * 3 if voxel_size_nm is not None else (float(downsample),) * 3
    axis_unit = "nm" if voxel_size_nm is not None else "vox"
    try:
        verts, faces, _, _ = measure.marching_cubes(vol, level=0.5, spacing=spacing)
    except (ValueError, RuntimeError) as e:
        lg.error(f"Marching cubes failed: {e}")
        print(f"  ERROR: Isometric render failed — {e}")
        return
    mesh = Poly3DCollection(verts[faces], alpha=0.75, linewidths=0)
    mesh.set_facecolor([0.3, 0.7, 1.0])  # light blue membrane colour
    mesh.set_edgecolor("none")
    fig = plt.figure(figsize=(7, 7))
    fig.patch.set_facecolor("black")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("black")
    ax.add_collection3d(mesh)
    # Axis limits from vertex extents
    for dim, (getter, setter) in enumerate(zip([verts[:, 0], verts[:, 1], verts[:, 2]],[ax.set_xlim, ax.set_ylim, ax.set_zlim])):
        pad = (getter.max() - getter.min()) * 0.05
        setter(getter.min() - pad, getter.max() + pad)
    ax.set_xlabel(f"X ({axis_unit})", color="white", labelpad=6)
    ax.set_ylabel(f"Y ({axis_unit})", color="white", labelpad=6)
    ax.set_zlabel(f"Z ({axis_unit})", color="white", labelpad=6)
    ax.tick_params(colors="white")
    for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
        pane.fill = False
        pane.set_edgecolor("none")
    # Isometric camera angle
    ax.view_init(elev=35.264, azim=45)
    ax.set_title("Isometric mask render", color="white", pad=10)
    out_file = output_path / "isometric_mask.png"
    fig.savefig(str(out_file), dpi=200, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    lg.info(f"Isometric mask render saved: {out_file}")
    print(f"  Isometric mask render saved: {out_file}")


# =========================
# DEFINE FUNCTION: make_isometric_mip
# =========================
def make_isometric_mip(data: numpy.ndarray, output_path: Path, downsample: int, voxel_size_nm):
    '''
    For a greyscale tomogram, compute a max intensity projection (MIP) from the
    isometric viewing direction. The volume is first downsampled, then rotated to
    the isometric angle (45° azimuth, 35.264° elevation), and the MIP is taken
    along the resulting Z axis (the viewer's line of sight).

    Args:
        data:           3D float/int numpy array (Z, Y, X)
        output_path:    output directory
        downsample:     integer downsampling factor
        voxel_size_nm:  voxel size in nm (or None)
    '''
    lg.info("Generating isometric MIP...")
    axis_unit = "nm" if voxel_size_nm is not None else "vox"
    vol = normalise_greyscale(data)
    if downsample > 1:
        vol = vol[::downsample, ::downsample, ::downsample]
        lg.info(f"Downsampled to {vol.shape} (factor {downsample})")
    lg.info("Rotating volume to isometric angle...")
    vol_iso = _rotate_isometric(vol)
    # MIP along the Z axis (line of sight after rotation)
    mip = numpy.max(vol_iso, axis=0)
    lg.info(f"MIP computed, output shape: {mip.shape}")
    # Calculate physical extent for axis labels if voxel size is known
    eff_vox = (voxel_size_nm * downsample) if voxel_size_nm is not None else float(downsample)
    ny, nx = mip.shape
    extent = [0, nx * eff_vox, 0, ny * eff_vox]
    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")
    im = ax.imshow(mip, cmap="gray", origin="upper", extent=extent, interpolation="bilinear")
    ax.set_xlabel(f"X ({axis_unit})", color="white")
    ax.set_ylabel(f"Y ({axis_unit})", color="white")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("white")
    ax.set_title("Isometric MIP (greyscale)", color="white", pad=8)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    cbar.set_label("Normalised intensity", color="white")
    out_file = output_path / "isometric_mip.png"
    fig.savefig(str(out_file), dpi=200, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    lg.info(f"Isometric MIP saved: {out_file}")
    print(f"  Isometric MIP saved: {out_file}")


# =========================
# DEFINE FUNCTION: main
# =========================
def main():
    # ---------------------
    # Print startup message
    # ---------------------
    print(f"\nEV VISUALISATION AUXILIARY SCRIPT")
    print(f"Full command: {' '.join(sys.argv)}\n")
    # ---------------------
    # Parse and validate arguments
    # ---------------------
    args = parse_arguments()
    verbosity_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    log_level = verbosity_levels[min(args.verbosity, len(verbosity_levels) - 1)]
    seg_file  = validate_input(args)
    out_dir   = validate_output(args)
    if args.downsample < 1:
        raise ValueError(f"--downsample must be >= 1, got {args.downsample}")
    if args.fps <= 0:
        raise ValueError(f"--fps must be > 0, got {args.fps}")
    # ---------------------
    # Set up logger configuration
    # ---------------------
    logging.basicConfig(format="%(asctime)s %(levelname)-10s %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=log_level)
    # ---------------------
    # Read MRC
    # ---------------------
    print(f"Reading: {seg_file}")
    data, voxel_size_nm = read_mrc(seg_file)
    is_mask = detect_mask(data)
    print(f"Volume shape (Z, Y, X): {data.shape}")
    print(f"Volume type: {'segmentation mask' if is_mask else 'greyscale tomogram'}")
    if voxel_size_nm:
        print(f"Voxel size: {voxel_size_nm:.4f} nm\n")
    else:
        print("Voxel size: not found in header (units will be voxels)\n")
    # ---------------------
    # Generate outputs
    # ---------------------
    if not args.no_movie:
        print("Generating Z-stack movie...")
        make_movie(data, out_dir, args.fps, is_mask, voxel_size_nm)
    else:
        print("Z-stack movie skipped (--no-movie).")
    if not args.no_iso:
        print("Generating isometric view...")
        if is_mask:
            make_isometric_mask(data, out_dir, args.downsample, voxel_size_nm)
        else:
            make_isometric_mip(data, out_dir, args.downsample, voxel_size_nm)
    else:
        print("Isometric view skipped (--no-iso).")
    print(f"\nAll outputs written to: {out_dir}\n")


if __name__ == "__main__":
    main()
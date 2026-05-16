'''
Benchmark the EValuator missing-wedge mitigations against a known ground truth

Workflow:
- Generates synthetic EVs across a range of true diameters
- Applies the Fourier missing-wedge degradation
- Runs each mitigation
- Reports recovered-diameter error vs ground truth
'''
# -- Import external dependencies
import os
import numpy as np
import pandas as pd
from rich import print

# -- Import internal functions
from evaluator.utils.missing_wedge import (
    anisotropic_closing_per_component,
    fill_lumen,
    fit_sphere_least_squares,
    lumen_diameter_from_volume,
    orientation_quality_score,
    xy_z_diameter_metrics,
)
from evaluator.utils.synthetic import (
    apply_fourier_missing_wedge,
    generate_ev_shell,
)

# -- Define internal constants
DIAMETERS = range(30,300,10)
REPLICATES = 30
VOXEL_SIZE = 2.0
TILT_RANGE = 60.0
DIAMETER_JITTER = 6.0
SHAPE_JITTER = 0.1
SEED = 0

# -- shell_voxel_diameter: returns float corresponding to raw shell voxel count
def shell_voxel_diameter(binary: np.ndarray, voxel_size_nm: float) -> float:
    '''
    Calculate equivalent diameter from raw shell voxel count
    '''
    n = int(binary.sum())
    if n == 0:
        return float('nan')
    return 2 * (3 * n * voxel_size_nm ** 3 / (4 * np.pi)) ** (1 / 3)

# -- run_benchmark: returns DataFrame containing calculated diameters with mitigations applied
def run_benchmark(
    diameters_nm: tuple[float, ...] = DIAMETERS,
    n_replicates: int = REPLICATES,
    voxel_size_nm: float = VOXEL_SIZE,
    tilt_range_deg: float = TILT_RANGE,
    diameter_jitter_pct: float = DIAMETER_JITTER,
    shape_jitter: float = SHAPE_JITTER,
    seed: int = SEED,
) -> pd.DataFrame:
    '''
    Run benchmark with realistic per-replicate variation
    '''
    # Seed random number generation
    rng = np.random.default_rng(seed)
    rows = []
    for nominal_d in diameters_nm:
        for rep in range(n_replicates):
            # Per-replicate variation
            d = float(rng.normal(nominal_d, nominal_d * diameter_jitter_pct / 100))
            offset = tuple(rng.uniform(-0.5, 0.5, size=3))
            axes = tuple(rng.normal(1.0, shape_jitter, size=3))
            # Generate synthetic EVs across specified diameter range
            shell, truth = generate_ev_shell(diameter_nm=d, voxel_size_nm=voxel_size_nm, centre_offset_voxels=offset, axis_ratios=axes)
            true_diameter = truth['diameter_nm']
            # Apply fourier missing wedge degradation
            degraded = apply_fourier_missing_wedge(shell, tilt_range_deg=tilt_range_deg)
            # Baseline (no mitigation)
            baseline_d = shell_voxel_diameter(degraded, voxel_size_nm)
            # Apply mitigation 1: anisotropic closing → shell-volume diameter
            closed = anisotropic_closing_per_component(degraded, z_radius=5, xy_radius=2)
            closed_d = shell_voxel_diameter(closed, voxel_size_nm)
            # Apply mitigation 2: sphere fit on raw degraded shell
            points = np.argwhere(degraded) * voxel_size_nm
            if len(points) >= 50:
                _, fit_radius, fit_rmse = fit_sphere_least_squares(points)
                fit_d = 2 * fit_radius
            else:
                fit_d = float('nan')
                fit_rmse = float('nan')
            # Apply mitigation 3: lumen-volume diameter (after closing + fill)
            filled = fill_lumen(closed)
            lumen_voxels = int(filled.sum() - closed.sum())
            lumen_d = lumen_diameter_from_volume(lumen_voxels, voxel_size_nm)
            # Apply mitigation 4: XY/Z diagnostic
            xyz = xy_z_diameter_metrics(degraded, voxel_size_nm)
            # Apply mitigation 5: orientation score
            orient = orientation_quality_score(degraded)
            # Add all results to DataFrame
            rows.append({
                'true_diameter_nm': true_diameter,
                'replicate': rep,
                'baseline_d_nm': baseline_d,
                'closed_d_nm': closed_d,
                'fit_d_nm': fit_d,
                'fit_rmse_nm': fit_rmse,
                'lumen_d_nm': lumen_d,
                'xy_d_nm': xyz['xy_diameter_nm'],
                'z_extent_nm': xyz['z_extent_nm'],
                'xy_z_ratio': xyz['xy_z_ratio'],
                'orientation_score': orient['score'],
                'anisotropy': orient['anisotropy'],
            })
    # Return dataframe  
    return pd.DataFrame(rows)

# -- summarise_errors: returns DataFrame of per-method error statistics
def summarise_errors(df: pd.DataFrame) -> pd.DataFrame:
    '''
    Compute per-method error statistics, pooling across diameters
    '''
    methods = {
        'baseline': 'baseline_d_nm',
        'anisotropic closing': 'closed_d_nm',
        'sphere fit': 'fit_d_nm',
        'lumen volume': 'lumen_d_nm',
        'XY-projection diameter': 'xy_d_nm',
    }
    rows = []
    for name, col in methods.items():
        err = df[col] - df['true_diameter_nm']
        rel = err / df['true_diameter_nm']
        rows.append({
            'method': name,
            'mean_signed_error_nm': float(err.mean()),
            'rmse_nm': float(np.sqrt((err ** 2).mean())),
            'mean_abs_rel_error_pct': float(100 * rel.abs().mean()),
            'max_abs_error_nm': float(err.abs().max()),
        })
    return pd.DataFrame(rows)

def calculate_errors(df: pd.DataFrame) -> pd.DataFrame:
    methods = {
        'baseline': 'baseline_d_nm',
        'anisotropic closing': 'closed_d_nm',
        'sphere fit': 'fit_d_nm',
        'lumen volume': 'lumen_d_nm',
        'XY-projection diameter': 'xy_d_nm',
    }
    err_df = df.copy()
    for name, col in methods.items():
        err = df[col] - df['true_diameter_nm']
        rel = err / df['true_diameter_nm']
        err_df.insert(loc=len(df.columns), column=f'{name}_error', value=err)
        err_df.insert(loc=len(df.columns), column=f'{name}_relative_error', value=rel)
    return err_df


def print_header():
    terminal_width = os.get_terminal_size().columns
    print(f'\n')
    print(f'{"="*terminal_width}')
    print(f'[bold]BENCHMARKING MISSING WEDGE[/bold]')
    print(
        f'Benchmarking parameters:\n'
        f'\t- True diameters: {DIAMETERS}\n'
        f'\t- Replicates per diameter: {REPLICATES}\n'
        f'\t- Voxel size (nm): {VOXEL_SIZE}\n'
        f'\t- Tilt range (°): {TILT_RANGE}\n'
        f'\t- Diameter jitter: {DIAMETER_JITTER}\n'
        f'\t- Shape jitter: {SHAPE_JITTER}\n'
        f'\t- RNG seed: {SEED}\n'
    )

# -- Entrypoint
if __name__ == '__main__':
    print_header()
    # Run benchmark
    df = run_benchmark()
    df_err = calculate_errors(df)
    # Print results
    print(f'[bold]Per-EV results (head):[/bold]')
    print(df.head(10).to_string(index=False))
    print(f'[bold]Per-method error summary:[/bold]')
    print(summarise_errors(df).to_string(index=False))
    print(f'\n\n')
    # Save result to disk
    df.to_csv('benchmark_missing_wedge_raw.csv', index=False)
    summarise_errors(df).to_csv('benchmark_missing_wedge_summary.csv', index=False)
    # df_err.to_csv('benchmark_missing_wedge_err.csv', index=False)
    df_err.to_csv('benchmark_missing_wedge_err.csv', index=False)
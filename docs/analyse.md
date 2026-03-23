# EValuator - analyse

## Overview
This command runs a pipeline which takes membrane segmentation masks produced by [MemBrain-seg](https://github.com/teamtomo/membrain-seg) and extracts quantitative morphological measurements for each EV identified in a tomogram. It is designed for use with denoised, CTF-corrected tomograms in `.mrc` format, and supports both single-tomogram and batch (HPC) workflows. The pipeline was developed for analysis of isolated EV preparations imaged by cryo-ET, but may be applicable to other membrane-bound structures of comparable scale (10s-100s nm).

## Output
Results are written to a `evaluator-analyse_results.csv` file with one row per detected EV. If the pipeline is run several times in the same output directory, subsequent result files will be written to `cryoet-ev_results-{n}.csv` where `{n}` increases by 1 per pipeline run. The following measurements are reported for each EV in all results files:
Column | Description | Units<sup>1</sup>
--|--|--
`tomogram` | File from which EV was identified |
`label` | Unique identifier for EV in the file given by `tomogram` |
`equiv_diameter_nm` | Calculated diameter of a sphere with equivalent volume | nm (rounded to 2 d.p.)
`major_axis_diameter` | Length of longest axis of the best-fit ellipsoid | nm (rounded to 2 d.p.)
`minor_axis_diameter` | Length of shortest axis of the best-fit ellipsoid | nm (rounded to 2 d.p.)
`aspect_ratio` | Ratio of major to minor axis diameters | unitless (rounded to 2 d.p.)
`eccentricity` | Degree of deviation from a sphere | unitless (0 ≤ e ≤ 1; 0 = perfect sphere; rounded to 2 d.p.)
`membrane_volume` | Volume of the segmented membrane | nm<sup>3</sup> (rounded to 2 d.p.)
`lumen_volume` | Volume of the EV lumen | nm<sup>3</sup> (rounded to 2 d.p.)
`surface_area` | Estimated membrane surface area | nm<sup>2</sup> (rounded to 2 d.p.)
`is_enclosed` | Boolean encoding whether EV is fully enclosed |
`closure_fill_ratio` | Measure of membrane closure completeness | unitless (0 < r ≤ 1; rounded to 4 d.p.)
`voxel_size_nm` | Size of voxel in nanometres (as read from MRC file header) |
`measurements_unit` | Units of measurements (nm or vox) |

<sup>1</sup> Units given here assume the voxel size in nanometres was read from the MRC file header. If this is not the case, units will not be scaled to physical units and will be in voxels/voxels<sup>3</sup>.

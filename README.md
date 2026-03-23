<div align="right">

[![Issues][issues-shield]][issues-url]
[![project_license][license-shield]][license-url]

</div>

# EValuator
A command line tool for automated morphological analysis and visualisation of extracellular vesicles (EVs) from cryo-electron tomography (cryo-ET) data.

## Overview
EValuator takes membrane segmentation masks produced by [MemBrain-seg](https://github.com/teamtomo/membrain-seg) and extracts quantitative morphological measurements for each EV identified in a tomogram. It was developed for the analysis of isolated EV preparations imaged by cryo-ET, but may be applicable to other membrane-bound structures of comparable scale (tens to hundreds of nm). All three commands support both single-file and batch workflows.

EValuator provides three main commands:

| Command | Description |
|---|---|
| [`analyse`](docs/analyse.md) | Run the morphological analysis pipeline on one or more segmentation files and write results to a CSV. |
| [`label`](docs/label.md) | Overlay EV segmentations onto the corresponding tomogram slices and save as an image. |
| [`visualise`](docs/visualise.md) | Generate a Z-stack movie and/or an isometric 3D surface render of a tomogram or segmentation mask. |

## Getting Help & Contributing
If you using this project and come across any bugs/issues, or if you have a feature request, please open an issue [here][issues-url]. 

Any contributions to this project are also very welcome! To contribute, please fork the repo, commit any changes, and then create a pull request.

## License

This repository is distributed under the GPL-3.0 license. See [LICENSE][license-url] for more information.

<br>

---
<p align="right"><a href="#cryoet-ev-post-processing-pipeline">^ Back to top</a></p>



<!-- MARKDOWN LINKS & IMAGES -->
[issues-shield]: https://img.shields.io/github/issues/holsam/cryoet-ev-post-processing.svg?style=for-the-badge&color=red
[issues-url]: https://github.com/holsam/cryoet-ev-post-processing/issues
[license-shield]: https://img.shields.io/github/license/holsam/cryoet-ev-post-processing.svg?style=for-the-badge&color=lightgray
[license-url]: https://github.com/holsam/cryoet-ev-post-processing/blob/main/LICENSE
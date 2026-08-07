# BioMed-RAGS

**A Low-Cost Open-Source Robotic Platform for Automated Optical Characterization of Complex Light Emitters**

> **Repository status:** This is a public pre-release repository. Hardware files, software, datasets, and supporting documentation are being reviewed and added progressively. The first complete versioned research release is not yet available.

## Overview

BioMed-RAGS is a low-cost, modular robotic platform for repeatable, spatially resolved characterization of optical emitters with different geometries. It supports cylindrical axial-azimuthal measurements and planar raster measurements using programmable scan paths and interchangeable detectors.

In the demonstrated configuration, a robotic arm and linear rail provide four controlled degrees of freedom for detector positioning. Two synchronized rotational stages provide a coordinated specimen-rotation axis for cylindrical measurements. The Python software coordinates motion, spectral acquisition, HDF5 data storage, processing, and visualization.

Device-specific drivers separate the measurement logic from the connected hardware, allowing sensors or motion components to be changed without rebuilding the complete control workflow.

## Demonstrated applications

The platform was evaluated using:

- Two light-diffusing fiber constructions for photodisinfection research
- A planar resin-printer backlight measured at multiple drive settings
- A bioreactor tube irradiance-mapping application example

## Key capabilities

- Automated cylindrical axial-azimuthal scanning
- Automated planar raster scanning
- Spatially resolved spectral-irradiance measurements
- Programmable scan ranges and step sizes
- Automatic spectrometer exposure adjustment
- Synchronized motion and spectral acquisition
- HDF5 storage of spectra and measurement coordinates
- Modular hardware-driver architecture
- Automated data processing and visualization
- Repeatability and reproducibility analysis

## Reported performance

| Measurement | Reported result |
|---|---:|
| Fiber peak irradiance, combined RSD | 1.21% (95% CI: 0.85–1.65%) |
| Planar area-mean irradiance, combined RSD | 0.78% (95% CI: 0.48–2.04%) |
| Fiber decay constant, combined RSD | 0.52% |
| Spectral peak stability across one 336-point scan | 0.06 nm |

These results describe the precision of the demonstrated measurement system. The study primarily evaluates repeatability and reproducibility rather than independent verification of absolute irradiance accuracy.

## Demonstrated configuration and cost

The demonstrated system uses a robotic arm on a 1000 mm linear rail, two synchronized rotational stages, a Raspberry Pi controller, and a spectrometer probe with a cosine corrector.

The automation layer used in this implementation cost approximately **USD 2,200**. This value is specific to the selected hardware and may change with component choice. The spectrometer, excitation source, and shared laboratory instruments are not included in this automation-layer estimate.

## Repository contents

| Directory | Contents |
|---|---|
| [`hardware/`](hardware/) | Bill of materials, mechanical designs, assembly photographs, and electronics documentation |
| [`firmware/`](firmware/) | Firmware and setup information for the rotational stages |
| [`software/`](software/) | Measurement-control and data-analysis software |
| [`data/`](data/) | Measurement datasets and processed results |
| [`docs/`](docs/) | Build, operation, calibration, and uncertainty documentation |
| [`examples/`](examples/) | Additional application examples and associated analyses |

These directories are currently being populated. Refer to the README inside each directory for its planned organization.

## Associated publication

This repository accompanies the manuscript:

> *A Low-Cost Open-Source Robotic Platform for Automated Optical Characterization of Complex Light Emitters*

The complete citation, DOI, and publication link will be added when they become available.

## Safety

This research platform includes moving robotic equipment and optical radiation sources. Appropriate laser or UV eye protection, beam control, access restriction, electrical precautions, and mechanical risk controls must be established before operation.

This repository does not replace a laboratory-specific risk assessment or the operating instructions supplied by equipment manufacturers.

## License and citation

License files and `CITATION.cff` metadata are being prepared and will be included before the first complete versioned release.

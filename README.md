# iFLM Slice Interpolator

> [!NOTE]
> **Full documentation:** https://chrisleethompson.github.io/scripts/iflm_slice_interpolator/

A PySide6/QML desktop utility that filters and z-interpolates image stacks produced by the Thermo Scientific Integrated Fluorescence Microscope (iFLM) software. Load the stack's `.tfs.xml` file, and the script repairs, background-subtracts, sharpens, and interpolates the images into virtual slices, then writes a new `.tfs.xml` file that imports directly into Thermo Scientific Maps.

This script is experimental. Many of the features are still being explored and tested.

## Documentation

Full documentation: https://chrisleethompson.github.io/scripts/iflm_slice_interpolator/

## Features

- **Load a stack** through its `.tfs.xml` file, by browsing or by dragging the file onto Catbug; stacks are processed per wavelength.
- **Hot pixel filter** that scans the whole stack for defects before repairing each slice.
- **Background subtraction** with Minimum Value, Gaussian Background, or Rolling Background algorithms, per image or normalized across the stack.
- **Unsharp masking** to sharpen features after background subtraction.
- **Slice interpolation** by Linear or Cubic Spline at an interpolation factor of 2 or 4.
- **Maps-ready output**: a new `Interpolated_*.tfs.xml` file next to the original and a `processed_images/` folder, with a Delete Data button to remove them.

## Requirements

- Python 3.11+
- PySide6 6.7.1+
- NumPy 2.2.5+
- OpenCV 4.8.1+ (`opencv-python`)
- SciPy 1.15.3+
- tifffile 2025.3.13+

AutoScript is not required. All packages above ship with the AutoScript 4.14 Python environment, where the script is developed and tested, so no extra installation is needed there.

## Installation

1. Download the latest release ZIP from the [Releases page](https://github.com/ChrisLeeThompson/iFLM_Slice_Interpolator/releases).
2. Extract it and copy the script folder to your desired location. The script does not connect to a microscope, so it can be installed on any PC that meets the requirements.
3. If you run the script with the AutoScript Python environment, no packages need to be installed. Otherwise, install them with:

   ```
   pip install -r requirements.txt
   ```

## Running

Run the main module from the script folder:

```
python iflm_slice_interpolator.py
```

The script also runs from the AutoScript Python interpreter or AutoScript Runner.

## Notes

- Output is written next to the original `.tfs.xml` file, not into the script folder.
- Linear Spline is often sufficient; Cubic Spline takes significantly longer. Low unsharp amounts and low Gaussian sigma values are often ideal.
- When stepping through the processed stack in Maps, non-interpolated and interpolated images can look slightly different, which shows as a flashing effect.

## License

MIT, see [LICENSE](LICENSE). Copyright (c) 2026 Christopher Thompson.

The Catbug artwork in `script_assets/` is not covered by the MIT license; see [LICENSE](LICENSE). PySide6 (Qt for Python) is licensed under the LGPLv3 and is used as an unmodified runtime dependency installed from PyPI; it is not distributed with this source.

## Contact

Developed by Chris Thompson with assistance from Anthropic's Claude. Questions and suggestions are welcome: [@ChrisLeeThompson](https://github.com/ChrisLeeThompson) on GitHub.

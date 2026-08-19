"""
Processing Parameters
This module defines the processing parameters dataclass that holds all parameters
for the image processing workflow.
"""

from dataclasses import dataclass


@dataclass
class ProcessingParams:
    """Container for all image processing parameters."""

    image_filter_method_index: int = 0
    interpolation_method_index: int = 0
    gaussian_background_sigma: int = 50
    unsharp_kernel_size: int = 3
    unsharp_gaussian_sigma: float = 0.5
    unsharp_amount: float = 7.0
    interpolation_factor: int = 2
    save_as_stack: bool = True                      # If true, single file tiff stack is saved for each channel (along with individual tiff files)
    global_background_normalization: bool = False   # Use global background normalization across the stack
    hot_pixel_filter: bool = False                  # Repair defective camera pixels (persistent defects + per-slice transients) before background subtraction
    hot_pixel_sigma: float = 6.0                    # Detection threshold, in local noise sigma

    def get_unsharp_ksize_tuple(self) -> tuple:
            """
            Convert kernel size to tuple for OpenCV GaussianBlur.
    
            : return: tuple: (0, 0) for auto-calculate mode, or (size, size) for manual mode
            """
            return (self.unsharp_kernel_size, self.unsharp_kernel_size)
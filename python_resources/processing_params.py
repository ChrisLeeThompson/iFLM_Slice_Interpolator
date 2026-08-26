"""
Processing Parameters

Defines the dataclass that carries every parameter of the image
processing workflow.
"""

from dataclasses import dataclass


@dataclass
class ProcessingParams:
    """Parameters for one processing run."""

    image_filter_method_index: int = 0
    interpolation_method_index: int = 0
    gaussian_background_sigma: int = 50
    unsharp_kernel_size: int = 3
    unsharp_gaussian_sigma: float = 0.5
    unsharp_amount: float = 3.0
    interpolation_factor: int = 2
    save_as_stack: bool = True                      # Also save a single multi-page TIFF stack per channel
    global_background_normalization: bool = False   # Use global background normalization across the stack
    hot_pixel_filter: bool = False                  # Repair defective camera pixels before background subtraction
    hot_pixel_sigma: float = 6.0                    # Detection threshold, in local noise sigma

    def get_unsharp_ksize_tuple(self) -> tuple:
        """
        Convert the kernel size to a tuple for OpenCV GaussianBlur.

        :return: (0, 0) for auto-calculate mode, or (size, size) for manual mode
        """
        return (self.unsharp_kernel_size, self.unsharp_kernel_size)

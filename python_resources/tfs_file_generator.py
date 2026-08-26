"""
TFS File Generator Module - Version 2

Generates a new TFS XML file for interpolated image stacks while preserving
the exact structure and formatting of the original file.

Copy the original parsed XML tree, then modify only what needs to change:
  - Per-ImageMatrix <Name> element: prepend "Interpolated_"
  - Per-image <Focus> values: use interpolated focus values
  - Per-image <RelativePath>: point to new interpolated TIFF files
  - Per-image <Guid>: generate unique GUID for each interpolated image
  - Per-image <Plane>: set correct plane index
  - Image ordering: interleave channels by plane (CRITICAL FOR IMPORT)
"""

import logging
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict
from copy import deepcopy
from .tfs_file_parser import TFSFileParser
from .slice_interpolator import calculate_interpolated_focus_values


logger = logging.getLogger(__name__)


# Name of the output directory created next to the original TFS file.
# Single source of truth - also used by the UI to locate/delete processed data.
PROCESSED_IMAGES_DIR_NAME = "processed_images"


def _split_tfs_name(original_tfs_path: Path) -> tuple[str, str]:
    """Split a TFS file name into (base name, extension), handling '.tfs.xml'."""
    original_name = original_tfs_path.name
    if original_name.lower().endswith('.tfs.xml'):
        return original_name[:-8], '.tfs.xml'
    if original_name.lower().endswith('.tfs'):
        return original_name[:-4], '.tfs'
    return original_tfs_path.stem, original_tfs_path.suffix


def get_interpolated_tfs_path(original_tfs_path: Path) -> Path:
    """
    Derive the output path for the interpolated TFS file.

    Single source of truth for the "Interpolated_*" naming - used both when
    generating the file and when the UI checks for / deletes existing output.

    :param original_tfs_path: Path to the original TFS file
    :return: Path of the interpolated TFS file (same directory as the original)
    """
    base_name, extension = _split_tfs_name(original_tfs_path)
    return original_tfs_path.parent / f"Interpolated_{base_name}{extension}"


def get_processed_images_dir(original_tfs_path: Path) -> Path:
    """
    Derive the per-stack output directory for processed images.

    Single source of truth for the output location - used by the worker to
    write, by the generator to build <RelativePath> entries, and by the UI
    to locate/delete processed data.  Each TFS file gets its own
    subdirectory so two stacks sitting in the same directory cannot
    overwrite each other's output.

    :param original_tfs_path: Path to the original TFS file
    :return: processed_images/<stack name>, next to the original TFS file
    """
    base_name, _ = _split_tfs_name(original_tfs_path)
    return original_tfs_path.parent / PROCESSED_IMAGES_DIR_NAME / base_name


def _generate_tfs_guid() -> str:
    """
    Generate a GUID in TFS format: {xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}

    Returns:
        str: Formatted UUID with curly braces and lowercase letters,
             matching the TFS file format
    """
    return f"{{{str(uuid.uuid4()).lower()}}}"


class TFSFileGenerator:
    """
    Generate a new TFS XML file for interpolated image stacks.
    
    Takes the original parsed TFS file and creates a modified copy with
    updated focus values and relative paths pointing to the interpolated
    images, while preserving all other metadata exactly.
    
    CRITICAL: Maintains proper image ordering (channels interleaved by plane)
    to match the original TFS file structure.
    """

    def __init__(
        self,
        original_parser: TFSFileParser,
        interpolation_factor: int,
        channel_dir_names: Dict[int, str],      # {channel_index: "Blue_L385", ...}
        channel_wavelength_tags: Dict[int, str] # {channel_index: "L385", ...}
    ):
        """
        Initialize the TFS generator.

        :param original_parser: Parsed original TFS file
        :param interpolation_factor: Same factor used for image interpolation
        :param channel_dir_names: Map from channel index to directory name
        :param channel_wavelength_tags: Map from channel index to wavelength tag
        """
        self._original_parser = original_parser
        self._interpolation_factor = interpolation_factor
        self._channel_dir_names = channel_dir_names
        self._channel_wavelength_tags = channel_wavelength_tags

        # Deep copy the original XML tree so we don't mutate the parser's data
        self._tree = deepcopy(original_parser.tree)
        self._root = self._tree.getroot()

        # Namespace handling (preserve original namespaces)
        self._namespaces = original_parser.namespaces

    def generate(self, output_path: Path) -> None:
        """
        Generate the new TFS file and write it to disk.

        :param output_path: Where to write the new TFS XML file
        """
        logger.info(f"Generating interpolated TFS file: {output_path.name}")

        # Step 1: Update the top-level <n> element
        self._update_top_level_name()

        # Step 2: Rebuild ALL images with correct interleaved ordering
        self._rebuild_all_images_with_correct_ordering()

        # Step 3: Write the modified tree to disk
        self._write_xml(output_path)

        logger.info(f"Successfully wrote interpolated TFS file: {output_path}")

    # ------------------------------------------------------------------
    # Update methods
    # ------------------------------------------------------------------

    def _update_top_level_name(self) -> None:
        """
        Update ALL <Name> elements within ImageMatrix sections to prepend "Interpolated_".
        
        This handles both the main stack and any additional ImageMatrix sections (e.g., MIP).
        
        Example: "Image_202508261029_stack_51" → "Interpolated_Image_202508261029_stack_51"
        Example: "Image_202508261029_stack_51_MIP" → "Interpolated_Image_202508261029_stack_51_MIP"
        """
        # Find ALL ImageMatrix elements
        image_matrices = self._root.findall('.//ImageMatrix')
        
        if not image_matrices:
            logger.warning("Could not find any ImageMatrix elements in TFS file")
            return
        
        updated_count = 0
        for matrix in image_matrices:
            # Find the <Name> element directly under this ImageMatrix
            name_elem = matrix.find('Name')
            if name_elem is not None and name_elem.text:
                original_name = name_elem.text
                
                # Only prepend "Interpolated_" if it's not already there
                if not original_name.startswith("Interpolated_"):
                    new_name = f"Interpolated_{original_name}"
                    name_elem.text = new_name
                    logger.debug(f"Updated ImageMatrix name: {original_name} → {new_name}")
                    updated_count += 1
                else:
                    logger.debug(f"ImageMatrix name already has 'Interpolated_' prefix: {original_name}")
            else:
                logger.warning(f"Could not find <Name> element in ImageMatrix")
        
        logger.info(f"Updated {updated_count} ImageMatrix name(s)")

    def _rebuild_all_images_with_correct_ordering(self) -> None:
        """
        Rebuild the entire Images section with proper ordering.
        
        CRITICAL ORDERING RULE:
        Images must be ordered by PLANE first, then by CHANNEL within each plane.
        
        For example with 3 channels and 5 planes:
          Plane 0: Ch0, Ch1, Ch2
          Plane 1: Ch0, Ch1, Ch2
          Plane 2: Ch0, Ch1, Ch2
          Plane 3: Ch0, Ch1, Ch2
          Plane 4: Ch0, Ch1, Ch2
        
        This matches the original TFS file format.
        """
        logger.info("Rebuilding images with correct plane/channel ordering")

        # Find the ImageMatrix and Images container
        image_matrix = self._root.find('.//ImageMatrix')
        if image_matrix is None:
            logger.error("Could not find ImageMatrix element in TFS file")
            return

        images_container = image_matrix.find('Images')
        if images_container is None:
            logger.error("Could not find Images container in TFS file")
            return

        # Get all channels
        channels = self._original_parser.get_channels()
        if not channels:
            logger.error("No channels found in original TFS file")
            return

        # Build a mapping: {channel_index: template_image_element}
        # We'll use the first image from each channel as a template
        channel_templates = {}
        for channel in channels:
            original_images = self._original_parser.get_images_for_channel(channel.index)
            if original_images:
                # Find the XML element for this image
                for img_elem in images_container.findall('Image'):
                    channel_elem = img_elem.find('.//Channel')
                    if channel_elem is not None and int(channel_elem.text) == channel.index:
                        channel_templates[channel.index] = img_elem
                        break

        if len(channel_templates) != len(channels):
            logger.warning(
                f"Found templates for {len(channel_templates)} channels, "
                f"expected {len(channels)}"
            )

        # Calculate interpolated focus values for each channel.
        # Channels without any parsed images are excluded here, matching the
        # worker (which skips them during processing) - they contribute no
        # <Image> entries to the output file.
        channel_focus_values = {}
        for channel in channels:
            original_focus = self._original_parser.get_focus_values_for_channel(channel.index)
            if not original_focus:
                logger.warning(
                    f"Channel '{channel.name}' has no images - excluded from generated TFS file"
                )
                continue
            interpolated_focus = calculate_interpolated_focus_values(
                original_focus,
                self._interpolation_factor
            )
            channel_focus_values[channel.index] = interpolated_focus

        if not channel_focus_values:
            raise ValueError("No channel in the TFS file has any images - nothing to generate")

        # Determine number of planes.  Upfront validation in the UI ensures all
        # non-empty channels have equal slice counts; the per-plane guard below
        # protects against unequal counts anyway.
        num_planes = max(len(v) for v in channel_focus_values.values())
        logger.info(f"Generating {num_planes} planes across {len(channel_focus_values)} channels")

        # Remove only the <Image> children.  Element.clear() would also wipe
        # the container's attributes, text, and any non-Image children.
        for old_img_elem in images_container.findall('Image'):
            images_container.remove(old_img_elem)

        # RelativePath entries are resolved relative to the generated XML,
        # which sits next to the original TFS file - so they start with the
        # same per-stack directory the worker writes into.
        stack_dir_name, _ = _split_tfs_name(self._original_parser.tfs_file_path)

        # Rebuild images with correct ordering: for each plane, add all channels.
        #
        # NOTE: each generated <Image> is a deep copy of the channel's first
        # image, with only Guid/Plane/Focus/RelativePath updated.  Per-image
        # Position (X/Y/Z/R/AT), Time, and TimeFrame therefore repeat the first
        # plane's values - in iFLM focus stacks only Focus varies per plane.
        # Channel/ImageMatrix GUIDs are deliberately kept identical to the
        # original file so internal cross-references stay valid.
        total_images_created = 0
        for plane_idx in range(num_planes):
            for channel in sorted(channels, key=lambda c: c.index):
                channel_idx = channel.index

                focus_list = channel_focus_values.get(channel_idx)
                if focus_list is None:
                    continue    # channel has no images - excluded above
                if plane_idx >= len(focus_list):
                    logger.warning(
                        f"Channel {channel_idx} has fewer planes ({len(focus_list)}) than "
                        f"expected ({num_planes}) - skipping plane {plane_idx}"
                    )
                    continue

                # Get the template for this channel
                template = channel_templates.get(channel_idx)
                if template is None:
                    logger.warning(f"No template found for channel {channel_idx}")
                    continue

                # Deep copy the template
                new_img_elem = deepcopy(template)

                # Generate and assign a unique GUID
                guid_elem = new_img_elem.find('Guid')
                if guid_elem is not None:
                    guid_elem.text = _generate_tfs_guid()
                else:
                    guid_elem = ET.SubElement(new_img_elem, 'Guid')
                    guid_elem.text = _generate_tfs_guid()

                # Update Plane index
                plane_elem = new_img_elem.find('.//Plane')
                if plane_elem is not None:
                    plane_elem.text = str(plane_idx)
                else:
                    logger.warning(f"No Plane element found for channel {channel_idx}, plane {plane_idx}")

                # Update Focus value
                focus_value = focus_list[plane_idx]
                focus_elem = new_img_elem.find('.//Focus')
                if focus_elem is not None:
                    focus_elem.text = f"{focus_value:.6f}"
                else:
                    logger.warning(f"No Focus element found for channel {channel_idx}, plane {plane_idx}")

                # Update RelativePath
                dir_name = self._channel_dir_names[channel_idx]
                wavelength_tag = self._channel_wavelength_tags[channel_idx]
                relative_path_elem = new_img_elem.find('RelativePath')
                if relative_path_elem is not None:
                    # Use Windows-style backslashes to match original TFS format
                    new_relative_path = (
                        f"{PROCESSED_IMAGES_DIR_NAME}\\{stack_dir_name}\\{dir_name}\\"
                        f"interpolated_stack_z{plane_idx:04d}_{wavelength_tag}.tif"
                    )
                    relative_path_elem.text = new_relative_path

                # Add the new image to the container
                images_container.append(new_img_elem)
                total_images_created += 1

            if (plane_idx + 1) % 10 == 0:
                logger.debug(f"  Created images for plane {plane_idx + 1}/{num_planes}")

        logger.info(f"Successfully created {total_images_created} interpolated image entries")
        logger.info(
            f"  Ordering: {num_planes} planes × {len(channel_focus_values)} channels "
            f"= {num_planes * len(channel_focus_values)} expected"
        )

    # ------------------------------------------------------------------
    # XML writing
    # ------------------------------------------------------------------

    def _write_xml(self, output_path: Path) -> None:
        """
        Write the modified XML tree to disk.

        Preserves the original formatting as much as possible, including
        the XML declaration and namespace declarations.

        :param output_path: Where to write the file
        """
        # Register namespaces to preserve prefixes
        for prefix, uri in self._namespaces.items():
            ET.register_namespace(prefix, uri)

        # Remove comment placeholders (empty text nodes left after ET removes comments)
        self._clean_whitespace(self._root)

        # Add pretty-printing indentation
        ET.indent(self._tree, space="  ", level=0)

        # Write to file with XML declaration
        self._tree.write(
            str(output_path),
            encoding='utf-8',
            xml_declaration=True,
            method='xml'
        )

        logger.debug(f"Wrote XML to {output_path}")

    def _clean_whitespace(self, elem):
        """
        Recursively remove excessive whitespace left by comment removal.
        
        ElementTree removes XML comments when parsing but leaves blank lines.
        This cleans them up.
        """
        # Remove leading/trailing whitespace from text
        if elem.text and elem.text.strip() == '':
            elem.text = None
        if elem.tail and elem.tail.strip() == '':
            elem.tail = None
        
        # Recurse into children
        for child in elem:
            self._clean_whitespace(child)


def generate_interpolated_tfs_file(
    original_tfs_path: Path,
    original_parser: TFSFileParser,
    interpolation_factor: int,
    channel_dir_names: Dict[int, str],
    channel_wavelength_tags: Dict[int, str]
) -> Path:
    """
    Convenience function to generate an interpolated TFS file.

    :param original_tfs_path: Path to the original TFS file
    :param original_parser: Parsed original TFS file
    :param interpolation_factor: Interpolation factor used
    :param channel_dir_names: Map from channel index to directory name
    :param channel_wavelength_tags: Map from channel index to wavelength tag
    :return: Path to the generated TFS file
    """
    output_path = get_interpolated_tfs_path(original_tfs_path)

    # Create the generator and run it
    generator = TFSFileGenerator(
        original_parser=original_parser,
        interpolation_factor=interpolation_factor,
        channel_dir_names=channel_dir_names,
        channel_wavelength_tags=channel_wavelength_tags
    )

    generator.generate(output_path)

    return output_path
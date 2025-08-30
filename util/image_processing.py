from pathlib import Path

from PIL import Image, ImageFile

Color = tuple[int, int, int]


def convert_hex_to_rgb(hex_color: str) -> Color:
    """
    Convert a hex color string to an RGB tuple.

    Parameters:
        hex_color (str): Hexadecimal color code, e.g., '#FF0000'.

    Returns:
        Color: The RGB color.
    """
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        raise ValueError("Input should be a 6-character hex color code.")
    # noinspection PyTypeChecker
    return Color(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def generate_image_from_template(template_image: ImageFile, old_colors: list[Color], new_colors: list[Color]) -> Image:
    """
    Create a new PNG image based on an input image, replacing specified colors with new colors.

    Parameters:
        template_image (ImageFile): The input image.
        old_colors (ColorList): RGB color tuples to replace.
        new_colors (ColorList): RGB color tuples to replace with (same length as 'old_colors').

    Returns:
        Image: The new templated image.
    """
    if len(old_colors) != len(new_colors):
        raise ValueError("The length of old_colors and new_colors lists must be the same.")

    pixels = template_image.load()
    new_image = Image.new("RGBA", template_image.size)
    new_pixels = new_image.load()

    for y in range(template_image.height):
        for x in range(template_image.width):
            r, g, b, a = pixels[x, y]
            new_color = (r, g, b)
            for target_color, replacement_color in zip(old_colors, new_colors):
                if (r, g, b) == target_color:
                    new_color = replacement_color
                    break
            new_pixels[x, y] = (*new_color, a)

    return new_image


def apply_template(template_config: dict, replacement_colors: list[Color]) -> Image:
    """
    Apply templating on an image with layers and color replacements.

    Parameters:
        template_config (dict): Configuration for templating.
        replacement_colors (ColorList): New colors for templating.

    Returns:
        Image: The templated image.
    """
    size = (100, 100)
    if 'template' in template_config:
        target_colors = [convert_hex_to_rgb(c) for c in template_config['templating_colors']]
        base_template = Image.open(Path('src') / template_config['template']).convert("RGBA")
        size = base_template.size
    composed_image = Image.new("RGBA", size).convert("RGBA")

    # Apply 'before' layer images if they exist
    if 'before' in template_config:
        for before_layer in template_config['before']:
            layer_image = Image.open(Path('src') / before_layer).convert("RGBA")
            composed_image = Image.alpha_composite(composed_image, layer_image)

    # Apply color replacements and compose with the template
    if 'template' in template_config:
        # noinspection PyUnboundLocalVariable
        replaced_image = generate_image_from_template(base_template, target_colors, replacement_colors)
        composed_image = Image.alpha_composite(composed_image, replaced_image)

    # Apply 'after' layer images if they exist
    if 'after' in template_config:
        for after_layer in template_config['after']:
            layer_image = Image.open(Path('src') / after_layer).convert("RGBA")
            composed_image = Image.alpha_composite(composed_image, layer_image)

    return composed_image


def nine_slice_scale(image: ImageFile, left: int, top: int, right: int, bottom: int, width: int, height: int,
                     tile=False, padding=(0, 0, 0, 0)) -> Image:
    """
    Scales an image using 9-slice scaling, accounting for padding.

    Args:
        image (ImageFile): The source image.
        left (int): Width of the left fixed slice.
        top (int): Height of the top fixed slice.
        right (int): Width of the right fixed slice.
        bottom (int): Height of the bottom fixed slice.
        width (int): Target width of the output image.
        height (int): Target height of the output image.
        tile (bool): Whether to tile or stretch the scalable parts.
        padding (tuple): Padding (left, top, right, bottom) to discard from the source image.

    Returns:
        PIL.Image.Image: The resized image with 9-slice scaling applied.
    """
    pad_left, pad_top, pad_right, pad_bottom = padding
    src_width, src_height = image.size

    # Crop the image to exclude the padding
    cropped_image = image.crop((pad_left, pad_top, src_width - pad_right, src_height - pad_bottom))
    cropped_width, cropped_height = cropped_image.size

    # Define the areas for slicing
    slices = slice_dict(bottom, cropped_height, cropped_width, left, right, top)

    # Calculate target areas
    target_slices = slice_dict(bottom, height, width, left, right, top)

    # Create the new image
    result = Image.new("RGBA", (width, height))

    for key, box in slices.items():
        region = cropped_image.crop(box)
        target_box = target_slices[key]
        target_width = target_box[2] - target_box[0]
        target_height = target_box[3] - target_box[1]

        if key in ["top", "center", "bottom"] and tile:
            # Tile horizontally
            tiled = Image.new("RGBA", (target_width, region.height))
            for x in range(0, target_width, region.width):
                tiled.paste(region, (x, 0))
            region = tiled
        elif key in ["left", "center", "right"] and tile:
            # Tile vertically
            tiled = Image.new("RGBA", (region.width, target_height))
            for y in range(0, target_height, region.height):
                tiled.paste(region, (0, y))
            region = tiled

        # Resize or use the tiled image
        if key == "center" and tile:
            tiled = Image.new("RGBA", (target_width, target_height))
            for x in range(0, target_width, region.width):
                for y in range(0, target_height, region.height):
                    tiled.paste(
                        region.crop((0, 0, min(region.width, target_width - x), min(region.height, target_height - y))),
                        (x, y))
            region = tiled
        elif not tile or key in ["top", "bottom", "left", "right", "center"]:
            region = region.resize((target_width, target_height), Image.Resampling.NEAREST)
        # noinspection PyTypeChecker
        result.paste(region, target_box[:2])

    return result


def slice_dict(bottom, height, width, left, right, top):
    return {"top_left": (0, 0, left, top), "top": (left, 0, width - right, top),
            "top_right": (width - right, 0, width, top),
            "left": (0, top, left, height - bottom),
            "center": (left, top, width - right, height - bottom),
            "right": (width - right, top, width, height - bottom),
            "bottom_left": (0, height - bottom, left, height),
            "bottom": (left, height - bottom, width - right, height),
            "bottom_right": (width - right, height - bottom, width, height), }


def make_transparent(image: Image, factor: float) -> Image:
    """
    Returns a copy of the given image with adjusted transparency.

    Args:
        image (Image): The input image.
        factor (float): Transparency scaling factor.

    Returns:
        Image: New RGBA image with adjusted transparency.
    """
    im = image.convert("RGBA")
    r, g, b, a = im.split()
    a = a.point(lambda i: int(i * factor))
    return Image.merge("RGBA", (r, g, b, a))

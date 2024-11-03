from PIL import Image, ImageFile
from pathlib import Path

Color = tuple[int, int, int]
ColorList = list[Color]


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
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def generate_image_from_template(template_image: ImageFile, old_colors: ColorList, new_colors: ColorList) -> Image:
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


def apply_template(template_config: dict, replacement_colors: ColorList) -> Image:
    """
    Apply templating on an image with layers and color replacements.

    Parameters:
        template_config (dict): Configuration for templating.
        replacement_colors (ColorList): New colors for templating.

    Returns:
        Image: The templated image.
    """
    target_colors = [convert_hex_to_rgb(c) for c in template_config['templating_colors']]
    base_template = Image.open(Path('src') / template_config['template']).convert("RGBA")
    composed_image = Image.new("RGBA", base_template.size).convert("RGBA")

    # Apply 'before' layer images if they exist
    if 'before' in template_config:
        for before_layer in template_config['before']:
            layer_image = Image.open(Path('src') / before_layer).convert("RGBA")
            composed_image = Image.alpha_composite(composed_image, layer_image)

    # Apply color replacements and compose with the template
    replaced_image = generate_image_from_template(base_template, target_colors, replacement_colors)
    composed_image = Image.alpha_composite(composed_image, replaced_image)

    # Apply 'after' layer images if they exist
    if 'after' in template_config:
        for after_layer in template_config['after']:
            layer_image = Image.open(Path('src') / after_layer).convert("RGBA")
            composed_image = Image.alpha_composite(composed_image, layer_image)

    return composed_image

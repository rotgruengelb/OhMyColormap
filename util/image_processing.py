from PIL import Image

Color = tuple[int, int, int]


def tint_image(image: Image, tint: Color) -> Image:
    """
    Apply a tint to an Image.

    Args:
        image (Image): Input grayscale or RGBA image.
        tint (Color): Tint color.

    Returns:
        Image: Tinted RGBA image.
    """
    im = image.convert("RGBA")
    pixels = im.load()
    tinted = Image.new("RGBA", im.size)
    tinted_pixels = tinted.load()

    tr, tg, tb = tint
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = pixels[x, y]
            intensity = r / 255.0
            nr = int(tr * intensity)
            ng = int(tg * intensity)
            nb = int(tb * intensity)
            tinted_pixels[x, y] = (nr, ng, nb, a)

    return tinted
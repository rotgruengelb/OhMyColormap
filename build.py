import json
import shutil
from pathlib import Path

from PIL import Image
from PIL.Image import Resampling

from util.image_processing import apply_template, convert_hex_to_rgb, nine_slice_scale
from util.pack import create_pack_metadata, compress_and_remove_directory, generate_random_word

SRC_PATH = Path('src')
BUILD_PATH = Path('build')


def main():
    # Load styles from JSON file
    with open(SRC_PATH / 'styles.json', 'r') as styles_file:
        styles = json.load(styles_file)

    # Load colors from JSON file
    with open(SRC_PATH / 'colors.json', 'r') as colors_file:
        colors = json.load(colors_file)

    for palette_name, palette in colors.items():
        palette_name: str = palette_name.split("/")[0]
        for style_name in palette['styles']:
            style_config = styles[style_name]

            # Generate pack name and set up working directory path
            pack_name = f"tooltip_{palette_name}.v{palette['version']}+{style_name}.v{style_config['version']}.{generate_random_word(8)}"
            print(f"Generating pack: {pack_name}")

            build_out_path = BUILD_PATH / pack_name

            # Convert hex colors to RGB tuples
            palette_colors = [convert_hex_to_rgb(c) for c in palette['colors']]

            # Generate images from templates
            background_image = apply_template(style_config['background'], palette_colors)
            frame_image = apply_template(style_config['frame'], palette_colors)

            # Output directory for sprites
            tooltip_path = build_out_path / 'assets' / 'minecraft' / 'textures' / 'gui' / 'sprites' / 'tooltip'
            tooltip_path.mkdir(parents=True, exist_ok=True)

            background_frame_image = Image.alpha_composite(background_image, frame_image)

            # Save images based on style configuration
            if 'merge_background_into_frame' in style_config and style_config['merge_background_into_frame']:
                background_frame_image.save(tooltip_path / 'frame.png')
                shutil.copytree(Path('util/assets/tooltip_use_only_frame'), tooltip_path, dirs_exist_ok=True)
            else:
                background_image.save(tooltip_path / 'background.png')
                frame_image.save(tooltip_path / 'frame.png')

            # Generate `pack.mcmeta` and add common files
            pack_description = f"Pride Tooltips | {palette['description_name']} {style_config['description_name']}"
            create_pack_metadata(build_out_path / 'pack.mcmeta', pack_description)
            shutil.copytree(Path('util/assets/tooltip_common'), tooltip_path, dirs_exist_ok=True)

            # Generate `pack.png`
            base_icon_image = nine_slice_scale(background_frame_image, 2, 2, 2, 2, 51, 36, False, (8, 8, 8, 8))
            text_overlay_image = Image.open(Path('util/assets/pack_png_tooltip_text.png'))
            unscaled_icon_image = Image.alpha_composite(base_icon_image, text_overlay_image)
            new_size = (unscaled_icon_image.width * 6, unscaled_icon_image.height * 6)
            scaled_image = unscaled_icon_image.resize(new_size, Resampling.NEAREST)
            pack_png = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            pack_png.paste(scaled_image, (0, 18))

            pack_png.save(build_out_path / 'pack.png')

            compress_and_remove_directory(build_out_path)


if __name__ == '__main__':
    main()

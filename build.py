import json
import shutil
from pathlib import Path
from util.image_processing import apply_template, convert_hex_to_rgb
from util.pack import create_pack_metadata, compress_and_remove_directory
from PIL import Image

SRC_PATH = Path('src')
BUILD_PATH = Path('build')

def main():
    # Load styles from JSON file
    with open(SRC_PATH / 'styles.json', 'r') as styles_file:
        styles = json.load(styles_file)

    # Load colors from JSON file
    with open(SRC_PATH / 'colors.json', 'r') as colors_file:
        colors = json.load(colors_file)

    for palette in colors:
        for style_name in palette['styles']:
            style_config = styles[style_name]

            # Generate pack name and set up working directory path
            pack_name = f"{palette['name']}-{style_name}-{palette['version']}+{style_config['version']}"
            build_out_path = BUILD_PATH / pack_name

            # Convert hex colors to RGB tuples
            palette_colors = [convert_hex_to_rgb(c) for c in palette['colors']]

            # Generate images from templates
            background_image = apply_template(style_config['background'], palette_colors)
            frame_image = apply_template(style_config['frame'], palette_colors)

            # Output directory for sprites
            tooltip_path = build_out_path / 'assets' / 'minecraft' / 'textures' / 'gui' / 'sprites' / 'tooltip'
            tooltip_path.mkdir(parents=True, exist_ok=True)

            # Save images based on style configuration
            if 'merge_background_into_frame' in style_config and style_config['merge_background_into_frame']:
                Image.alpha_composite(background_image, frame_image).save(tooltip_path / 'frame.png')
                shutil.copytree(Path('util/assets/tooltip_use_only_frame'), tooltip_path, dirs_exist_ok=True)
            else:
                background_image.save(tooltip_path / 'background.png')
                frame_image.save(tooltip_path / 'frame.png')

            # Generate `pack.mcmeta` and add common files
            pack_description = f"PrideTooltips | {palette['description_name']} {style_config['description_name']}"
            create_pack_metadata(build_out_path / 'pack.mcmeta', pack_description)
            shutil.copytree(Path('util/assets/tooltip_common'), tooltip_path, dirs_exist_ok=True)

            compress_and_remove_directory(build_out_path)


if __name__ == '__main__':
    main()

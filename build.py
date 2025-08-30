import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

import dotenv
from PIL import Image
from PIL.Image import Resampling

from util.image_processing import apply_template, convert_hex_to_rgb, nine_slice_scale, make_transparent
from util.pack import (create_pack_metadata, compress_and_remove_directory, generate_random_word,
                       modrinth_markdown_template, )

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)


def main():
    start_time = datetime.now()
    logger.info("Starting build process")

    # Paths and environment
    src = Path('src')
    build = Path('build')
    build_user = dotenv.get_key('.env', 'BUILD_USER') or "Unknown"

    try:
        # Load styles
        styles_path = src / 'styles.json'
        logger.info(f"Loading styles from {styles_path}")
        with open(styles_path, 'r') as styles_file:
            styles = json.load(styles_file)

        # Load colors
        colors_path = src / 'colors.json'
        logger.info(f"Loading colors from {colors_path}")
        with open(colors_path, 'r') as colors_file:
            colors = json.load(colors_file)

    except Exception as e:
        logger.error(f"Failed to load configuration files: {e}", exc_info=True)
        return

    for palette_name, palette in colors.items():
        palette_name: str = palette_name.split("/")[0]
        logger.info(f"Processing palette '{palette_name}'")

        for style_name in palette['styles']:
            style_config = styles[style_name]
            logger.info(f"\t\tUsing style '{style_name}'")

            # Generate identifiers
            pack_slug = f"tooltip_{palette_name}+{style_name}"
            pack_version = f"v{palette['version']}+v{style_config['version']}"
            pack_name = f"tooltip_{palette_name}.v{palette['version']}+{style_name}.v{style_config['version']}"
            pack_friendly_name = f"{palette['description_name']} Tooltip ({style_config['description_name']})"
            color_palette_collection = palette.get('collection_id', "not_available")
            build_pack_dir_name = f"{pack_name}.{generate_random_word(8)}"

            build_out_path = build / pack_name
            build_zip_collect_path = build_out_path / build_pack_dir_name
            logger.debug(f"\t\tBuild output path: {build_zip_collect_path}")

            try:
                # Convert colors
                palette_colors = [convert_hex_to_rgb(c) for c in palette['colors']]
                logger.debug(f"\t\tConverted palette colors: {palette_colors}")

                # Generate images
                background_image = apply_template(style_config['background'], palette_colors)
                frame_image = apply_template(style_config['frame'], palette_colors)
                background_frame_image = Image.alpha_composite(background_image, frame_image)

                # Save tooltip images
                tooltip_path = build_zip_collect_path / 'assets' / 'minecraft' / 'textures' / 'gui' / 'sprites' / 'tooltip'
                tooltip_path.mkdir(parents=True, exist_ok=True)

                if style_config.get('merge_background_into_frame', False):
                    logger.debug("\t\tMerging background into frame")
                    background_frame_image.save(tooltip_path / 'frame.png')
                    shutil.copytree(Path('src/resources/tooltip_use_only_frame'), tooltip_path, dirs_exist_ok=True)
                else:
                    logger.debug("\t\tSaving background and frame separately")
                    background_image.save(tooltip_path / 'background.png')
                    frame_image.save(tooltip_path / 'frame.png')

                # Metadata + resources
                create_pack_metadata(build_zip_collect_path / 'pack.mcmeta', pack_friendly_name)
                shutil.copytree(Path('src/resources/tooltip_common'), tooltip_path, dirs_exist_ok=True)

                # Pack.png
                logger.debug("\t\tGenerating pack.png")
                base_icon_image = nine_slice_scale(background_frame_image, 2, 2, 2, 2, 51, 36, False, (8, 8, 8, 8))
                base_icon_image = make_transparent(base_icon_image, 0.92)
                text_overlay_image = Image.open(src / 'resources' / 'pack_png_tooltip_text.png')

                unscaled_icon_image = Image.alpha_composite(
                    Image.open(src / 'resources' / 'pack_png_tooltip_background.png'), base_icon_image)
                unscaled_icon_image = Image.alpha_composite(unscaled_icon_image, text_overlay_image)

                new_size = (unscaled_icon_image.width * 6, unscaled_icon_image.height * 6)
                scaled_image = unscaled_icon_image.resize(new_size, Resampling.NEAREST)

                pack_png = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
                pack_png.paste(scaled_image, (0, 18))

                pack_png.save(build_zip_collect_path / 'pack.png')
                pack_png.save(build_out_path / f'{pack_name}.png')

                # Compress
                logger.debug(f"\t\tCompressing and finalizing {pack_name}")
                compress_and_remove_directory(build_zip_collect_path)

                # Markdown template
                context = {"pack_slug": pack_slug, "pack_friendly_name": pack_friendly_name, "pack_name": pack_name,
                           "pack_version": pack_version, "color_palette_name": palette['description_name'],
                           "color_palette_collection": color_palette_collection,
                           "color_palette_formated": f"* {'\n* '.join(palette['colors'])}",
                           "style_explanation": f"{style_config['description_name']} = {style_config['explanation']}",
                           "build_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "build_user": build_user, }
                modrinth_markdown_template(src / 'resources' / 'modrinth.md', build_out_path / 'modrinth.md', context)

                logger.info(f"\t\tFinished building {pack_name}")

            except Exception as e:
                logger.error(f"\t\tError while processing {pack_name}: {e}", exc_info=True)

    logger.info(f"Build process completed in {int((datetime.now() - start_time).total_seconds() * 1000)}ms")


if __name__ == '__main__':
    main()

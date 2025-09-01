import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

import dotenv
from PIL import Image
from PIL.Image import Resampling

from util.image_processing import apply_template, convert_hex_to_rgb, nine_slice_scale, make_transparent
from util.logger import get_logger
from util.markdown import appy_modrinth_markdown_template
from util.pack import (create_pack_metadata, compress_and_remove_directory, generate_random_word)

logger = get_logger(__name__)

def main():
    start_time = datetime.now()
    logger.info("Starting build task")

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

    district_pack_count = 0
    for palette_name, palette in colors.items():
        palette_name: str = palette_name.split("/")[0]
        logger.info(f"Processing palette '{palette_name}'")
        palette_colors = [convert_hex_to_rgb(c) for c in palette['colors']]
        logger.debug(f"\tConverted palette colors: {palette_colors}")

        for style_name in palette['styles']:
            style_config = styles[style_name]
            logger.info(f"\tUsing style '{style_name}'")

            # Generate identifiers
            pack_slug = f"tooltip_{palette_name}+{style_name}"
            pack_version = f"v{palette['version']}+v{style_config['version']}"
            pack_name = f"tooltip_{palette_name}.v{palette['version']}+{style_name}.v{style_config['version']}"
            pack_friendly_name = f"{palette['description_name']} Tooltip ({style_config['description_name']})"
            color_palette_collection = palette.get('collection_id', "!remove_line!")
            build_pack_dir_name = f"{pack_name}.{generate_random_word(8)}"
            pack_friendly_name_description = pack_friendly_name.replace(" Tooltip", "")
            if "Flag" in pack_friendly_name_description:
                pack_friendly_name_description = f"a {pack_friendly_name_description}"
            else:
                pack_friendly_name_description = f"be {pack_friendly_name_description}"

            build_out_path = build / pack_slug
            build_zip_collect_path = build_out_path / build_pack_dir_name
            logger.debug(f"\t\tBuild output path: {build_zip_collect_path}")

            try:
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

                logger.debug("\t\tGenerating pack.png & gallery image")

                # Build base icon with transparency
                base_icon_image = nine_slice_scale(background_frame_image, 2, 2, 2, 2, 51, 36, False, (8, 8, 8, 8))
                base_icon_image = make_transparent(base_icon_image, 0.92)

                # Load overlay images
                tooltip_text = Image.open(src / "resources" / "pack_png_tooltip_text.png")
                tooltip_bg = Image.open(src / "resources" / "pack_png_tooltip_background.png")
                pack_gallery = Image.open(src / "resources" / "pack_gallery_background.png")

                # Compose unscaled icon
                pack_png = Image.alpha_composite(tooltip_bg, base_icon_image)
                pack_png = Image.alpha_composite(pack_png, tooltip_text)

                # Compose unscaled gallery
                icon_with_text = Image.alpha_composite(base_icon_image, tooltip_text)
                pack_gallery.alpha_composite(icon_with_text, (50, 10))

                # Scale up unscaled pack png
                scaled_pack_png = pack_png.resize((pack_png.width * 6, pack_png.height * 6), Resampling.NEAREST)

                # Scale up unscaled gallery
                pack_gallery = pack_gallery.resize((pack_gallery.width * 6, pack_gallery.height * 6), Resampling.NEAREST)

                # Final pack.png (256x256)
                pack_png = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
                pack_png.paste(scaled_pack_png, (0, 18), mask=scaled_pack_png)

                # Save outputs
                pack_png.save(build_zip_collect_path / "pack.png")
                pack_png.save(build_out_path / f"{pack_name}.png")
                pack_gallery.save(build_out_path / f"gallery_{pack_name}.png")

                # Compress
                logger.debug(f"\t\tCompressing and finalizing {pack_name}")
                compress_and_remove_directory(build_zip_collect_path)

                # Markdown template
                context = {"pack_slug": pack_slug, "pack_friendly_name": pack_friendly_name, "pack_name": pack_name,
                           "pack_friendly_name_description": pack_friendly_name_description,
                           "pack_version": pack_version, "color_palette_name": palette["description_name"],
                           "color_palette_collection": color_palette_collection,
                           "color_palette_formated": "* " + "\n* ".join(palette["colors"]),
                           "style_explanation": f"{style_config['description_name']} = {style_config['explanation']}",
                           "build_time": datetime.now().astimezone().isoformat(timespec="seconds"),
                           "build_user": build_user}

                Path(build_out_path / "modrinth.md").write_text(
                    appy_modrinth_markdown_template(Path(src / "resources" / "modrinth.md").read_text(encoding="utf-8"), context), encoding="utf-8")

                logger.info(f"\t\tFinished building {pack_name}")
                district_pack_count += 1

            except Exception as e:
                logger.error(f"\t\tError while processing {pack_name}: {e}", exc_info=True)

    logger.info(f"Total packs built: {district_pack_count}")
    logger.info(f"Done: build task completed in {int((datetime.now() - start_time).total_seconds() * 1000)}ms.")


if __name__ == '__main__':
    main()

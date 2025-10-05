import json
from datetime import datetime
from pathlib import Path

import dotenv
from PIL import Image

from util.image_processing import tint_image, Color
from util.logger import get_logger
from util.markdown import appy_modrinth_markdown_template
from util.pack import (compress_and_remove_directory, generate_random_word, friendly_pack_biome, create_pack_metadata)

logger = get_logger(__name__)

def main():
    start_time = datetime.now()
    logger.info("Starting build task")

    # Paths and environment
    src = Path('src')
    build = Path('build')
    build_user = dotenv.get_key('.env', 'BUILD_USER') or "Unknown"
    build_banner = bool(dotenv.get_key('.env', 'BUILD_BANNER')) or False

    if build_banner:
        (build / "banner").mkdir(parents=True, exist_ok=True)

    try:

        # Load colormaps
        colormaps = {}
        for json_file in (src / "colormaps").glob('*.json'):
            key = json_file.stem
            with open(json_file, 'r') as f:
                colormaps[key] = json.load(f)

        # Load metadata
        meta_path = src / 'meta.json'
        logger.info(f"Loading metadata from {meta_path}")
        with open(meta_path, 'r') as meta_file:
            meta = json.load(meta_file)

    except Exception as e:
        logger.error(f"Failed to load configuration files: {e}", exc_info=True)
        return

    district_pack_count = 0
    build_banner_count = 0
    for colormap_name, biomes in colormaps.items():
        logger.info(f"Processing colormap '{colormap_name}'")

        for biome_name, biome_config in biomes.items():
            logger.info(f"\tProcessing biome '{biome_name}'")

            pack_slug = f"{biome_name}_{colormap_name}_everywhere"
            pack_version = f"v{meta["global_version"]}"
            pack_name = f"{pack_slug}.{pack_version}"
            pack_friendly_name = f"{friendly_pack_biome(biome_name)} {friendly_pack_biome(colormap_name)} Everywhere!"
            biome_collection = biome_config.get('collection_id', "!remove_line!")
            build_pack_dir_name = f"{pack_name}.{generate_random_word(8)}"

            build_out_path = build / pack_slug
            build_zip_collect_path = build_out_path / build_pack_dir_name
            logger.debug(f"\t\tBuild output path: {build_zip_collect_path}")

            try:
                # Generate colormap
                colormap_path = build_zip_collect_path / 'assets' / 'minecraft' / 'textures' / 'colormap'
                colormap_path.mkdir(parents=True, exist_ok=True)

                hex_color = biome_config['color']
                hex_color = hex_color.lstrip('#')
                if len(hex_color) != 6:
                    raise ValueError("Input should be a 6-character hex color code.")
                # noinspection PyTypeChecker
                color = Color(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
                colormap_png = Image.new("RGBA", (256, 256), (*color, 255))
                colormap_png.save(colormap_path / f"{colormap_name}.png")

                logger.debug("\t\tGenerating pack.png & gallery image")

                # Metadata
                create_pack_metadata(build_zip_collect_path / 'pack.mcmeta', pack_friendly_name, 0)

                # Load overlay images
                colormap_resources_path = src / "resources" / colormap_name

                banner_overlay = tint_image(Image.open(colormap_resources_path / "banner_overlay.png"), color)
                banner = Image.open(colormap_resources_path / "banner.png")
                banner.alpha_composite(banner_overlay)
                icon_overlay = tint_image(Image.open(colormap_resources_path / "icon_overlay.png"), color)
                icon = Image.open(colormap_resources_path / "icon.png")
                icon.alpha_composite(icon_overlay)

                # Save outputs
                icon.save(build_zip_collect_path / "pack.png")
                icon.save(build_out_path / f"{pack_name}.png")
                banner.save(build_out_path / f"gallery_{pack_name}.png")
                if build_banner and colormap_name == "grass":
                    build_banner_count += 1
                    build_banner_save_path = (build / "banner" / f"{build_banner_count}.png")
                    banner.save(build_banner_save_path)
                    logger.info("\t\tSaved banner image to " + str(build_banner_save_path))

                # Compress
                logger.debug(f"\t\tCompressing and finalizing {pack_name}")
                compress_and_remove_directory(build_zip_collect_path)

                # Markdown template
                context = {"pack_slug": pack_slug, "pack_friendly_name": pack_friendly_name, "pack_name": pack_name,
                           "pack_version": pack_version, "color": biome_config['color'],
                           "biome_name": friendly_pack_biome(biome_name), "colormap_name": friendly_pack_biome(colormap_name),
                           "biome_list_formatted": "* " + "\n* ".join(biome_config["biomes"]),
                           "build_time": datetime.now().astimezone().isoformat(timespec="seconds"),
                           "build_user": build_user}

                Path(build_out_path / "modrinth.md").write_text(
                    appy_modrinth_markdown_template(Path(src / "resources" / "modrinth.md").read_text(encoding="utf-8"), context), encoding="utf-8")


                logger.info(f"\t\tFinished building {pack_name}")
                district_pack_count += 1

            except Exception as e:
                logger.error(f"\t\tError while processing {pack_name}: {e}", exc_info=True)
    if build_banner:
        file_list = ""
        for i in range(0, build_banner_count):
            file_list += f"{i}.png "
        logger.info(file_list)
    logger.info(f"Total packs built: {district_pack_count}")
    logger.info(f"Done: build task completed in {int((datetime.now() - start_time).total_seconds() * 1000)}ms.")


if __name__ == '__main__':
    main()

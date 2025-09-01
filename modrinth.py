import sys
from datetime import datetime
from pathlib import Path

import dotenv

from util.logger import get_logger
from util.markdown import markdown_with_frontmatter_to_dict, appy_modrinth_markdown_template
from util.modrinth.api import ModrinthAPI, ModrinthAPIError
from util.modrinth.types import (NewProject, ProjectType, SideSupport, ProjectUpdate, GalleryImage, )

logger = get_logger(__name__)


def project_check_for_files(project_dir: Path, required_files: list[str]) -> bool:
    """Verify that all required files exist in a project directory."""
    missing_files = [f for f in required_files if not (project_dir / f).is_file()]
    if missing_files:
        logger.warning(f"\tMissing required file(s): {', '.join(missing_files)}")
        return False
    return True


def load_project_data(project_dir: Path) -> dict:
    """Load and parse the modrinth.md file for a project."""
    modrinth_md = project_dir / "modrinth.md"
    if not modrinth_md.is_file():
        logger.warning(f"\tMissing 'modrinth.md' file.")
        return {}
    logger.info(f"\tFound 'modrinth.md'.")
    return markdown_with_frontmatter_to_dict(modrinth_md)


def check(modrinth_api: ModrinthAPI) -> None:
    """Check projects in the build directory for required files and Modrinth existence."""
    start_time = datetime.now()
    logger.info("Starting modrinth/check task")

    build = Path("build")
    if not build.is_dir():
        logger.error("Build directory does not exist. Run the build task first.")
        return

    count, count_files, count_modrinth = 0, 0, 0

    for project_dir in build.iterdir():
        if not project_dir.is_dir():
            continue
        count += 1
        logger.info(f"Checking project '{project_dir.name}'.")

        project_data = load_project_data(project_dir)
        if not project_data:
            continue

        required_files = [project_data["version_file"], project_data["icon_file"], project_data["gallery_file"], ]
        if project_check_for_files(project_dir, required_files):
            logger.info("\tAll required files present.")
            count_files += 1

        try:
            modrinth_api.get_project(project_data["slug"])
            logger.info(f"\tProject '{project_data['slug']}' exists on Modrinth.")
            count_modrinth += 1
        except ModrinthAPIError as e:
            logger.warning(f"\tProject '{project_data['slug']}' not found on Modrinth.")
            logger.debug(f"\tError details: {e}", exc_info=True)

    logger.info(f"Checked {count} project(s): "
                f"{count_files} with all required files, "
                f"{count_modrinth} exist on Modrinth.")
    logger.info(
        f"Done: modrinth/check task completed in {int((datetime.now() - start_time).total_seconds() * 1000)}ms.")


def create(modrinth_api: ModrinthAPI, modrinth_org_id: str) -> None:
    """Create new projects on Modrinth based on build directory metadata."""
    start_time = datetime.now()
    logger.info("Starting modrinth/create task")

    build = Path("build")
    if not build.is_dir():
        logger.error("Build directory does not exist. Run the build task first.")
        return

    for project_dir in build.iterdir():
        if not project_dir.is_dir():
            continue

        logger.info(f"Creating project '{project_dir.name}'.")

        project_data = load_project_data(project_dir)
        if not project_data:
            continue

        required_files = [project_data["version_file"], project_data["icon_file"], project_data["gallery_file"]]
        if not project_check_for_files(project_dir, required_files):
            logger.warning("\tSkipping due to missing files.")
            continue

        # Skip if already exists
        try:
            modrinth_api.get_project(project_data["slug"])
            logger.info(f"\tProject '{project_data['slug']}' already exists, skipping.")
            continue
        except ModrinthAPIError:
            logger.info(f"\tProject '{project_data['slug']}' does not exist, creating...")

        # Create project
        try:
            new_project = modrinth_api.create_project(
                NewProject(slug=project_data["slug"],
                           title=project_data["name"],
                           description=project_data["summary"],
                           categories=["gui", "themed", "tweaks"],
                           additional_categories=["vanilla-like", "utility", "simplistic", "equipment", "16x"],
                           project_type=ProjectType.RESOURCEPACK,
                           body=project_data["body"],
                           client_side=SideSupport.REQUIRED,
                           server_side=SideSupport.UNSUPPORTED,
                           organization_id=modrinth_org_id,
                           license_id="CC-BY-SA-4.0"),
                icon_path=project_dir / project_data["icon_file"])
            logger.info(f"\tCreated '{new_project['slug']}' successfully.")

            logger.info(f"\tGallery image for '{new_project['slug']}' uploaded successfully.")
        except ModrinthAPIError as e:
            logger.error(f"\tFailed to create project '{project_data['slug']}': {e}", exc_info=True)

    logger.info(
        f"Done: modrinth/create task completed in {int((datetime.now() - start_time).total_seconds() * 1000)}ms.")


def update(modrinth_api: ModrinthAPI) -> None:
    """Update existing projects on Modrinth."""
    start_time = datetime.now()
    logger.info("Starting modrinth/create task")

    build = Path("build")
    if not build.is_dir():
        logger.error("Build directory does not exist. Run the build task first.")
        return

    for project_dir in build.iterdir():
        if not project_dir.is_dir():
            continue

        logger.info(f"Updating project '{project_dir.name}'.")

        project_data = load_project_data(project_dir)
        if not project_data:
            continue

        required_files = [project_data["version_file"], project_data["icon_file"], project_data["gallery_file"]]
        if not project_check_for_files(project_dir, required_files):
            logger.warning("\tSkipping due to missing files.")
            continue

        # Skip if not found
        try:
            # Upload gallery image
            project_to_update = modrinth_api.get_project(project_data["slug"])
            logger.info(f"\tProject '{project_data['slug']}' already exists, updating...")

            gallery_file = project_dir / project_data["gallery_file"]
            gallery = project_to_update.get("gallery", [])
            if len(gallery) > 0:
                modrinth_api.delete_gallery_image(project_data["gallery_file"], gallery[0]["url"])
            modrinth_api.add_gallery_image(id_or_slug=project_data["slug"],
                                           image=GalleryImage(image_path=gallery_file,
                                                              ext=gallery_file.suffix.lstrip("."), featured=True,
                                                              title="Modified Tooltip (Banner)",
                                                              description="Banner showing the modified Tooltip. Cursor texture from the Minecraft Cursor Mod by fishstiz."))
            project_to_update = modrinth_api.get_project(project_data["slug"])
            new_gallery_image_url = project_to_update["gallery"][0]["url"]
            new_body = appy_modrinth_markdown_template(project_data["body"],
                                                       context={"upload_gallery_url": new_gallery_image_url})

            # Create project
            modrinth_api.modify_project(
                project_data["slug"],
                ProjectUpdate(
                    title=project_data["name"],
                    description=project_data["summary"],
                    categories=["gui", "themed", "tweaks"],
                    additional_categories=["vanilla-like", "utility", "simplistic", "equipment", "16x"],
                    body=new_body,
                    client_side=SideSupport.REQUIRED,
                    server_side=SideSupport.UNSUPPORTED,
                    license_id="CC-BY-SA-4.0")
            )
        except ModrinthAPIError:
            logger.info(
                f"\tProject '{project_data['slug']}' does not exist or had errors occur during updating, continuing")


def publish(modrinth_api: ModrinthAPI) -> None:
    """Handle publish workflow."""
    logger.info("Not yet implemented.")


def main() -> None:
    modrinth_token = dotenv.get_key(".env", "MODRINTH_TOKEN")
    modrinth_api_url = dotenv.get_key(".env", "MODRINTH_API_URL")
    modrinth_org_id = dotenv.get_key(".env", "MODRINTH_ORG_ID")

    if not modrinth_token or not modrinth_api_url or not modrinth_org_id:
        logger.error("Missing or incomplete Modrinth configuration in .env file.")
        return

    modrinth_api = ModrinthAPI(token=modrinth_token, api_url=modrinth_api_url,
                               user_agent="Pridecraft-Studios/pridetooltips (daniel+pridetooltips@rotgruengelb.net)", )

    subtask = sys.argv[1] if len(sys.argv) > 2 else input("Enter subtask: ")
    match subtask:
        case "check":
            check(modrinth_api)
        case "create":
            create(modrinth_api, modrinth_org_id)
        case "update":
            update(modrinth_api)
        case "publish":
            publish(modrinth_api)
        case _:
            logger.error(f"Unknown subtask '{subtask}'")


if __name__ == "__main__":
    main()

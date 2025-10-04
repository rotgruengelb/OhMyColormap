import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import List

import dotenv

from util.logger import get_logger
from util.markdown import markdown_with_frontmatter_to_dict, appy_modrinth_markdown_template
from util.modrinth.api import ModrinthAPI, ModrinthAPIError
from util.modrinth.types import (
    NewProject, ProjectType, SideSupport, ProjectUpdate,
    GalleryImage, NewVersion, VersionType,
)

logger = get_logger(__name__)
BUILD_DIR = Path("build")


def project_check_for_files(project_dir: Path, required_files: list[str]) -> bool:
    missing_files = [f for f in required_files if not (project_dir / f).is_file()]
    if missing_files:
        logger.warning(f"[{project_dir.name}] Missing required file(s): {', '.join(missing_files)}")
        return False
    return True


def load_project_data(project_dir: Path) -> dict:
    modrinth_md = project_dir / "modrinth.md"
    if not modrinth_md.is_file():
        logger.warning(f"[{project_dir.name}] Missing 'modrinth.md' file.")
        return {}
    logger.info(f"[{project_dir.name}] Found 'modrinth.md'.")
    return markdown_with_frontmatter_to_dict(modrinth_md)


def verify_build_dir() -> bool:
    if not BUILD_DIR.is_dir():
        logger.error("Build directory does not exist. Run the build task first.")
        return False
    return True


def iterate_projects():
    return (d for d in BUILD_DIR.iterdir() if d.is_dir())


def run_task(task_name: str):
    logger.info(f"Starting modrinth/{task_name} task")
    return datetime.now()


def log_task_completion(task_name: str, start_time: datetime):
    elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    logger.info(f"Done: modrinth/{task_name} task completed in {elapsed_ms}ms.")


def fetch_org_projects(modrinth_api: ModrinthAPI, org_id: str) -> dict:
    """Fetch all projects for the organization and index them by slug."""
    try:
        projects = modrinth_api.get_organization_projects(org_id)
        return {proj['slug']: proj for proj in projects}
    except ModrinthAPIError as e:
        logger.error(f"Failed to fetch organization projects: {e}", exc_info=True)
        return {}


def handle_files_and_project_data(project_dir: Path) -> dict | None:
    project_data = load_project_data(project_dir)
    slug = project_data.get("slug", "???")
    if not project_data:
        logger.debug(f"[{project_dir.name}] No valid project data")
        return None

    required_files = [project_data["version_file"], project_data["icon_file"], project_data["gallery_file"]]
    if not project_check_for_files(project_dir, required_files):
        logger.warning(f"[{project_dir.name}] Skipping due to missing files.")
        return None

    return project_data


def do_for_each_project(org_projects, action_fn, skip_if_exists=False, skip_if_missing=False, log_queue_msg=None, all_org_mode=False):
    """ Helper to deduplicate the project iteration logic for create/update/publish """
    results = []
    if all_org_mode:
        project_dirs = {projects['slug']: None for projects in org_projects.values()}
        for slug in project_dirs:
            if log_queue_msg:
                logger.info(log_queue_msg.format(dir=slug, slug=slug))
            results.append(action_fn(slug, None, org_projects.get(slug)))
    else:
        project_dirs = {directories.name: directories for directories in iterate_projects()}

        for project_path in project_dirs:
            project_path = BUILD_DIR / project_path
            project_data = handle_files_and_project_data(project_path)
            if not project_data:
                continue

            slug = project_data["slug"]
            project_exists = slug in org_projects
            if skip_if_exists and project_exists:
                logger.info(f"[{project_path.name}] Project already exists, skipping.")
                continue
            if skip_if_missing and not project_exists:
                logger.warning(f"[{project_path.name}] Project not found on Modrinth, skipping.")
                continue

            if log_queue_msg:
                logger.info(log_queue_msg.format(dir=project_path.name, slug=slug))
            results.append(action_fn(project_path, project_data, org_projects.get(slug)))
    return results


def check(modrinth_api: ModrinthAPI, modrinth_org_id: str) -> None:
    if not verify_build_dir():
        return

    start_time = run_task("check")
    total, files_ok, modrinth_ok = 0, 0, 0

    org_projects = fetch_org_projects(modrinth_api, modrinth_org_id)

    for project_dir in iterate_projects():
        total += 1
        project_data = load_project_data(project_dir)
        slug = project_data.get("slug", "???")
        logger.info(f"[{project_dir.name}] Checking project...")
        if not project_data:
            logger.debug(f"[{project_dir.name}] Skipping due to missing or invalid modrinth.md")
            continue

        required_files = [project_data["version_file"], project_data["icon_file"], project_data["gallery_file"]]
        if project_check_for_files(project_dir, required_files):
            logger.info(f"[{project_dir.name}] All required files present.")
            files_ok += 1

        if slug in org_projects:
            logger.info(f"[{project_dir.name}] Project exists on Modrinth.")
            modrinth_ok += 1
        else:
            logger.warning(f"[{project_dir.name}] Project not found on Modrinth.")

    logger.info(f"Checked {total} project(s): {files_ok} with all required files, {modrinth_ok} exist on Modrinth.")
    log_task_completion("check", start_time)


def create(modrinth_api: ModrinthAPI, modrinth_org_id: str) -> None:
    if not verify_build_dir():
        return

    start_time = run_task("create")
    org_projects = fetch_org_projects(modrinth_api, modrinth_org_id)

    def make_create_function(project_dir, project_data, _):
        slug = project_data["slug"]
        dir_name = project_dir.name
        def _wrapped():
            try:
                result = modrinth_api.create_project(
                    NewProject(
                        slug=slug,
                        title=project_data["name"],
                        description="......",
                        categories=[],
                        additional_categories=[],
                        project_type=ProjectType.RESOURCEPACK,
                        body="......",
                        client_side=SideSupport.REQUIRED,
                        server_side=SideSupport.UNSUPPORTED,
                        organization_id=modrinth_org_id,
                        license_id="CC-BY-SA-4.0"
                    ),
                    icon_path=project_dir / project_data["icon_file"]
                )
                return {"slug": slug, "dir_name": dir_name, "success": True, "result": result}
            except ModrinthAPIError as e:
                return {"slug": slug, "dir_name": dir_name, "success": False, "ModrinthAPIError": e}
        return _wrapped

    to_create = do_for_each_project(
        org_projects, make_create_function,
        skip_if_exists=True,
        log_queue_msg="[{{dir}}]\\t Queued for creation..."
    )

    if to_create:
        try:
            results = modrinth_api.parallel_requests(to_create)
            for result in results:
                slug = result['slug']
                dir_name = result.get("dir_name", "???")
                if result.get("success"):
                    logger.info(f"[{dir_name}] Created successfully.")
                else:
                    logger.error(f"[{dir_name}] Failed to create: {result.get('ModrinthAPIError')}", exc_info=True)
        except ModrinthAPIError:
            logger.error("Failed to create some projects.", exc_info=True)

    log_task_completion("create", start_time)

def update_gallery(modrinth_api: ModrinthAPI, modrinth_org_id: str) -> None:
    start_time = run_task("update_gallery")
    org_projects = fetch_org_projects(modrinth_api, modrinth_org_id)

    def make_update_gallery(project_dir, project_data, project):
        slug = project_data["slug"]
        dir_name = project_dir.name

        def _update():
            logger.info(f"[{dir_name}] Updating gallery...")
            try:
                if not project:
                    logger.warning(f"[{dir_name}] Project does not exist, skipping gallery update.")
                    return {"slug": slug, "dir_name": dir_name, "success": False, "error": "Missing project"}

                gallery_file = project_dir / project_data["gallery_file"]
                if project.get("gallery"):
                    logger.info(f"[{dir_name}] Deleting old gallery image...")
                    try:
                        modrinth_api.delete_gallery_image(project_data["gallery_file"], project["gallery"][0]["url"])
                    except ModrinthAPIError as img_ex:
                        logger.warning(f"[{dir_name}] Could not delete old gallery image: {img_ex}")
                        logger.debug(traceback.format_exc())

                logger.info(f"[{dir_name}] Adding new gallery image...")
                modrinth_api.add_gallery_image(
                    id_or_slug=slug,
                    image=GalleryImage(
                        image_path=gallery_file,
                        ext=gallery_file.suffix.lstrip("."),
                        featured=True,
                        title="Modified Tooltip (Banner)",
                        description="Banner showing the modified Tooltip. Cursor texture from the Minecraft Cursor Mod by fishstiz."
                    )
                )

                logger.info(f"[{dir_name}] Gallery updated successfully.")
                return {"slug": slug, "dir_name": dir_name, "success": True}
            except ModrinthAPIError as e:
                logger.error(f"[{dir_name}] Gallery update failed: {e}", exc_info=True)
                return {"slug": slug, "dir_name": dir_name, "success": False, "error": e}

        return _update

    to_update = do_for_each_project(org_projects, make_update_gallery, skip_if_missing=True,
                                    log_queue_msg="[{dir}] Queued for gallery update...")
    if to_update:
        try:
            modrinth_api.parallel_requests(to_update)
        except ModrinthAPIError:
            logger.error("Some gallery updates failed.", exc_info=True)

    log_task_completion("update_gallery", start_time)


def update_data(modrinth_api: ModrinthAPI, modrinth_org_id: str) -> None:
    start_time = run_task("update_data")
    org_projects = fetch_org_projects(modrinth_api, modrinth_org_id)

    def make_update_data(project_dir, project_data, project):
        slug = project_data["slug"]
        dir_name = project_dir.name

        def _update():
            logger.info(f"[{dir_name}] Updating metadata...")
            try:
                if not project:
                    logger.warning(f"[{dir_name}] Project does not exist, skipping metadata update.")
                    return {"slug": slug, "dir_name": dir_name, "success": False, "error": "Missing project"}

                refreshed_project = modrinth_api.get_project(slug)
                gallery_url = refreshed_project["gallery"][0]["url"] if refreshed_project.get("gallery") else None
                new_body = appy_modrinth_markdown_template(
                    project_data["body"],
                    context={"upload_gallery_url": gallery_url}
                )

                modrinth_api.modify_project(
                    refreshed_project["id"],
                    ProjectUpdate(
                        title=project_data["name"],
                        description=project_data["summary"],
                        categories=project_data["primary_categories"].split(" "),
                        additional_categories=project_data["additional_categories"].split(" "),
                        issues_url=project_data["issues_url"],
                        source_url=project_data["source_url"],
                        discord_url=project_data["discord_url"],
                        body=new_body,
                        license_id=project_data["license_id"],
                    )
                )
                logger.info(f"[{dir_name}] Metadata updated successfully.")
                return {"slug": slug, "dir_name": dir_name, "success": True}
            except ModrinthAPIError as e:
                logger.error(f"[{dir_name}] Metadata update failed: {e}", exc_info=True)
                return {"slug": slug, "dir_name": dir_name, "success": False, "error": e}

        return _update

    to_update = do_for_each_project(org_projects, make_update_data, skip_if_missing=True,
                                    log_queue_msg="[{dir}] Queued for metadata update...")
    if to_update:
        try:
            modrinth_api.parallel_requests(to_update)
        except ModrinthAPIError:
            logger.error("Some metadata updates failed.", exc_info=True)

    log_task_completion("update_data", start_time)


def update_body(modrinth_api: ModrinthAPI, modrinth_org_id: str) -> None:
    start_time = run_task("update_body")
    org_projects = fetch_org_projects(modrinth_api, modrinth_org_id)

    def make_update_data(project_dir, project_data, project):
        slug = project_data["slug"]
        dir_name = project_dir.name

        def _update():
            logger.info(f"[{dir_name}] Updating body...")
            try:
                if not project:
                    logger.warning(f"[{dir_name}] Project does not exist, skipping body update.")
                    return {"slug": slug, "dir_name": dir_name, "success": False, "error": "Missing project"}

                refreshed_project = modrinth_api.get_project(slug)
                gallery_url  = refreshed_project["gallery"][0]["url"] if refreshed_project.get("gallery") else None

                new_body = appy_modrinth_markdown_template(
                    project_data["body"],
                    context={"upload_gallery_url": gallery_url}
                )

                modrinth_api.modify_project(
                    refreshed_project["id"],
                    ProjectUpdate(
                        body=new_body,
                    )
                )
                logger.info(f"[{dir_name}] Body updated successfully.")
                return {"slug": slug, "dir_name": dir_name, "success": True}
            except ModrinthAPIError as e:
                logger.error(f"[{dir_name}] Body update failed: {e}", exc_info=True)
                return {"slug": slug, "dir_name": dir_name, "success": False, "error": e}

        return _update

    to_update = do_for_each_project(org_projects, make_update_data, skip_if_missing=True,
                                    log_queue_msg="[{dir}] Queued for body update...")
    if to_update:
        try:
            modrinth_api.parallel_requests(to_update)
        except ModrinthAPIError:
            logger.error("Some body updates failed.", exc_info=True)

    log_task_completion("update_body", start_time)


def update_icon(modrinth_api: ModrinthAPI, modrinth_org_id: str) -> None:
    start_time = run_task("update_icon")
    org_projects = fetch_org_projects(modrinth_api, modrinth_org_id)

    def make_update_icon(project_dir, project_data, project):
        slug = project_data["slug"]
        dir_name = project_dir.name

        def _update():
            logger.info(f"[{dir_name}] Updating project icon...")
            try:
                if not project:
                    logger.warning(f"[{dir_name}] Project does not exist, skipping icon update.")
                    return {"slug": slug, "dir_name": dir_name, "success": False, "error": "Missing project"}

                refreshed_project = modrinth_api.get_project(slug)
                icon_file = project_dir / project_data["icon_file"]

                modrinth_api.change_project_icon(
                    refreshed_project["id"],
                    icon_path=icon_file,
                    ext=icon_file.suffix.lstrip(".")
                )

                logger.info(f"[{dir_name}] Icon updated successfully.")
                return {"slug": slug, "dir_name": dir_name, "success": True}
            except ModrinthAPIError as e:
                logger.error(f"[{dir_name}] Icon update failed: {e}", exc_info=True)
                return {"slug": slug, "dir_name": dir_name, "success": False, "error": e}

        return _update

    to_update = do_for_each_project(org_projects, make_update_icon, skip_if_missing=True,
                                    log_queue_msg="[{dir}] Queued for icon update...")
    if to_update:
        try:
            modrinth_api.parallel_requests(to_update)
        except ModrinthAPIError:
            logger.error("Some icon updates failed.", exc_info=True)

    log_task_completion("update_icon", start_time)


def update(modrinth_api: ModrinthAPI, modrinth_org_id: str) -> None:
    if not verify_build_dir():
        return

    match sys.argv[2] if len(sys.argv) > 2 else input("Enter update-subtask: "):
        case "all":
            update_icon(modrinth_api, modrinth_org_id)
            update_gallery(modrinth_api, modrinth_org_id)
            update_data(modrinth_api, modrinth_org_id)
        case "icon":
            update_icon(modrinth_api, modrinth_org_id)
        case "gallery":
            update_gallery(modrinth_api, modrinth_org_id)
        case "data":
            update_data(modrinth_api, modrinth_org_id)
        case "body":
            update_body(modrinth_api, modrinth_org_id)
        case _:
            logger.error("Unknown update-subtask")


def publish(modrinth_api: ModrinthAPI, modrinth_org_id: str) -> None:
    if not verify_build_dir():
        return

    src = Path('src')
    try:
        # Load metadata
        meta_path = src / 'meta.json'
        logger.info(f"Loading metadata from {meta_path}")
        with open(meta_path, 'r') as meta_file:
            meta = json.load(meta_file)

    except Exception as e:
        logger.error(f"Failed to load configuration files: {e}", exc_info=True)
        return

    start_time = run_task("publish")
    game_versions = get_game_versions(modrinth_api)
    org_projects = fetch_org_projects(modrinth_api, modrinth_org_id)

    def make_publish_fn(project_dir, project_data, project):
        slug = project_data["slug"]
        dir_name = project_dir.name
        def _wrapped():
            try:
                version_name = f"{str(project_data['name']).replace(meta["redundant_removable_info"], "")} {project_data['version_version']}"
                if len(version_name) > 64:
                    version_name = version_name.replace("Frame-only", "Fr...")
                    version_name = version_name.replace("Alt-BG", "A...")
                    version_name = version_name.replace("Background/Frame", "B.../Fr...")
                    version_name = version_name.replace("Monochrome", "Mono...")

                result = modrinth_api.create_version(
                    NewVersion(
                        name=version_name,
                        version_number=project_data["version_version"],
                        project_id=project["id"],
                        loaders=["minecraft"],
                        version_type=VersionType.RELEASE,
                        dependencies=[],
                        game_versions=game_versions
                    ),
                    [project_dir / project_data["version_file"]],
                    project_data["version_file"]
                )
                return {"slug": slug, "dir_name": dir_name, "success": True, "result": result}
            except ModrinthAPIError as e:
                return {"slug": slug, "dir_name": dir_name, "success": False, "ModrinthAPIError": e}
        return _wrapped

    to_publish = do_for_each_project(
        org_projects, make_publish_fn,
        skip_if_missing=True,
        log_queue_msg="[{dir}] Queued for publish..."
    )

    if to_publish:
        try:
            results = modrinth_api.parallel_requests(to_publish)
            for result in results:
                slug = result['slug']
                dir_name = result.get("dir_name", "???")
                if result.get("success"):
                    logger.info(f"[{dir_name}] Published successfully.")
                else:
                    logger.error(f"[{dir_name}] Failed to publish: {result.get('ModrinthAPIError')}", exc_info=True)
        except ModrinthAPIError as e:
            logger.error("Failed to publish some projects.", exc_info=True)

    log_task_completion("publish", start_time)




def submit(modrinth_api: ModrinthAPI, modrinth_org_id: str) -> None:
    if not verify_build_dir():
        return

    start_time = run_task("submit")
    org_projects = fetch_org_projects(modrinth_api, modrinth_org_id)

    def make_submit_function(project_name, project_data, project):
        def _submit():
            try:
                if not project:
                    logger.warning(f"[{project_name}] Project does not exist or had errors, continuing.")
                    return {"slug": project_name, "dir_name": project_name, "success": False, "ModrinthAPIError": "Does not exist on Modrinth"}
                if project.get("status") == "processing":
                    logger.info(f"[{project_name}] Project already in processing state, skipping.")
                    return {"slug": project_name, "dir_name": project_name, "success": True}

                logger.info(f"[{project_name}] Submitting project...")
                modrinth_api.modify_project(
                    project["id"],
                    ProjectUpdate(
                        status="processing"
                    )
                )
                logger.info(f"[{project_name}] Submitted successfully.")
                return {"slug": project_name, "dir_name": project_name, "success": True}
            except ModrinthAPIError as e:
                logger.error(f"[{project_name}] Unexpected error whist submitting: {e}", exc_info=True)
                return {"slug": project_name, "dir_name": project_name, "success": False, "ModrinthAPIError": e}
        return _submit

    to_update = do_for_each_project(
        org_projects, make_submit_function,
        skip_if_missing=True,
        log_queue_msg="[{dir}] Queued for submit...",
        all_org_mode=True
    )

    if to_update:
        try:
            results = modrinth_api.parallel_requests(to_update)
            for result in results:
                slug = result['slug']
                dir_name = result.get("dir_name", "???")
                if result.get("success"):
                    logger.info(f"[{dir_name}] Submitted successfully.")
                else:
                    logger.error(f"[{dir_name}] Failed to submit: {result.get('ModrinthAPIError')}", exc_info=True)
        except ModrinthAPIError as e:
            logger.error("Failed to submit some projects.", exc_info=True)

    log_task_completion("submit", start_time)



def get_game_versions(modrinth_api: ModrinthAPI) -> List[str]:
    cut_versions = modrinth_api.get_game_versions_until("24w36a")
    return [version["version"] for version in cut_versions]


def workspace_1(modrinth_api, modrinth_org_id) -> None:
    # delete all project folders of projects that have a status other than "draft"
    if not verify_build_dir():
        return
    start_time = run_task("workspace")
    org_projects = fetch_org_projects(modrinth_api, modrinth_org_id)
    deleted_count = 0
    for project_dir in iterate_projects():
        project_data = load_project_data(project_dir)
        if not project_data:
            logger.debug(f"[{project_dir.name}] No valid project data")
            continue
        slug = project_data["slug"]
        project = org_projects.get(slug)
        if not project:
            logger.warning(f"[{project_dir.name}] Project not found on Modrinth, skipping.")
            continue
        if project.get("status") != "draft":
            try:
                for item in project_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        for subitem in item.rglob('*'):
                            if subitem.is_file():
                                subitem.unlink()
                        item.rmdir()
                project_dir.rmdir()
                deleted_count += 1
                logger.info(f"[{project_dir.name}] Deleted project folder.")
            except Exception as e:
                logger.error(f"[{project_dir.name}] Failed to delete project folder: {e}", exc_info=True)

    logger.info(f"Deleted {deleted_count} project folder(s).")
    log_task_completion("workspace", start_time)


def workspace_2(modrinth_api: ModrinthAPI, modrinth_org_id: str) -> None:
    # delete all project folders that already have their current version published on Modrinth
    if not verify_build_dir():
        return
    start_time = run_task("workspace_2")
    org_projects = fetch_org_projects(modrinth_api, modrinth_org_id)
    deleted_count = 0

    for project_dir in iterate_projects():
        project_data = load_project_data(project_dir)
        if not project_data:
            logger.debug(f"[{project_dir.name}] No valid project data")
            continue

        slug = project_data["slug"]
        current_version = project_data.get("version_version")
        if not current_version:
            logger.warning(f"[{project_dir.name}] Missing 'version_version' in project data, skipping.")
            continue

        project = org_projects.get(slug)
        if not project:
            logger.warning(f"[{project_dir.name}] Project not found on Modrinth, skipping.")
            continue

        try:
            versions = modrinth_api.get_project_versions(slug)
            published_versions = [v["version_number"] for v in versions]

            if current_version in published_versions:
                for item in project_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        for subitem in item.rglob('*'):
                            if subitem.is_file():
                                subitem.unlink()
                        item.rmdir()
                project_dir.rmdir()
                deleted_count += 1
                logger.info(f"[{project_dir.name}] Deleted project folder (version {current_version} already published).")
            else:
                logger.info(f"[{project_dir.name}] Current version {current_version} not published yet, keeping folder.")

        except ModrinthAPIError as e:
            logger.error(f"[{project_dir.name}] Failed to check versions: {e}", exc_info=True)

    logger.info(f"Deleted {deleted_count} project folder(s).")
    log_task_completion("workspace_2", start_time)



def main() -> None:
    modrinth_token = dotenv.get_key(".env", "MODRINTH_TOKEN")
    modrinth_api_url = dotenv.get_key(".env", "MODRINTH_API_URL")
    modrinth_org_id = dotenv.get_key(".env", "MODRINTH_ORG_ID")

    if not modrinth_token or not modrinth_api_url or not modrinth_org_id:
        logger.error("Missing or incomplete Modrinth configuration in .env file.")
        return

    modrinth_api = ModrinthAPI(
        token=modrinth_token,
        api_url=modrinth_api_url,
        user_agent="rotgruengelb/ohmycolormap (daniel+ohmycolormap@rotgruengelb.net)"
    )

    match sys.argv[1] if len(sys.argv) > 1 else input("Enter subtask: "):
        case "check":
            check(modrinth_api, modrinth_org_id)
        case "create":
            create(modrinth_api, modrinth_org_id)
        case "update":
            update(modrinth_api, modrinth_org_id)
        case "publish":
            publish(modrinth_api, modrinth_org_id)
        case "submit":
            submit(modrinth_api, modrinth_org_id)
        case "workspace_1":
            workspace_1(modrinth_api, modrinth_org_id)
        case "workspace_2":
            workspace_2(modrinth_api, modrinth_org_id)
        case _:
            logger.error("Unknown subtask")


if __name__ == "__main__":
    main()
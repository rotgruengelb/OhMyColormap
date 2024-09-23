import pathlib
import shutil


def structure_copy(scr_root_dir: pathlib.Path, scr_file_path: pathlib.Path, dst_root_dir: pathlib.Path) -> None:
    """
    Copies a file from a source directory to a destination directory, preserving the directory structure.

    Args:
        scr_root_dir (pathlib.Path): The root directory of the directory structure to be preserved.
        scr_file_path (pathlib.Path): The path to the file to be copied.
        dst_root_dir (pathlib.Path): The root directory where the file should be copied to.

    Returns:
        None
    """
    relative_path = scr_file_path.relative_to(scr_root_dir)
    dest_path = dst_root_dir / relative_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(scr_file_path, dest_path)

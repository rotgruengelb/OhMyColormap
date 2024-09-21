import os
import shutil


def structure_copy(scr_root_dir: os.PathLike, scr_file_path: os.PathLike, dst_root_dir: os.PathLike) -> None:
    """
    Copies a file from a source directory to a destination directory, preserving the directory structure.

    Args:
        scr_root_dir (os.PathLike): The root directory of the directory structure to be preserved.
        scr_file_path (os.PathLike): The path to the file to be copied.
        dst_root_dir (os.PathLike): The root directory where the file should be copied to.

    Returns:
        None
    """
    relative_path = os.path.relpath(scr_file_path, start=scr_root_dir)
    dest_path = os.path.join(dst_root_dir, relative_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    shutil.copy2(scr_file_path, dest_path)

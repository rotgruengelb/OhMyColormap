import os
import shutil


def structure_copy(source_dir: os.PathLike, source_file: os.PathLike, dest_dir: os.PathLike) -> None:
    """
    Copies a file from a source directory to a destination directory, preserving the directory structure.

    Args:
        source_dir (os.PathLike): The root directory of the source file.
        source_file (os.PathLike): The path to the source file to be copied.
        dest_dir (os.PathLike): The root directory where the file should be copied to.

    Returns:
        None
    """
    relative_path = os.path.relpath(source_file, start=source_dir)
    dest_path = os.path.join(dest_dir, relative_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    shutil.copy2(source_file, dest_path)
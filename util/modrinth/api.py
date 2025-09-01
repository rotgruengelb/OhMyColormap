from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests

from util.modrinth.types import NewProject, DictKV, NewVersion, GalleryImage, ProjectUpdate


class ModrinthAPIError(Exception):
    """Custom error for Modrinth API failures."""

    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class ModrinthAPI:
    def __init__(self, token: str, api_url: str = "https://api.modrinth.com/v2", user_agent: str = "requests/2.32.5"):
        self.api_url = api_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": token, "User-Agent": user_agent, })

    def _request(self, method: str, endpoint: str, **kwargs) -> DictKV:
        """Send a request and handle errors uniformly."""
        url = f"{self.api_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            if response.text:
                return response.json()
            return {}
        except requests.HTTPError as e:
            try:
                error_json = response.json()
            except Exception:
                error_json = {"error": response.text}
            raise ModrinthAPIError(str(e), status_code=response.status_code, response=error_json) from e

    def create_project(self, project: NewProject, icon_path: Optional[Path] = None) -> DictKV:
        """Create a new project on Modrinth."""
        payload = {k: v for k, v in project.__dict__.items() if v is not None}
        if "donation_urls" in payload:
            payload["donation_urls"] = [du.__dict__ for du in payload["donation_urls"]]

        files = {"icon": icon_path.open("rb")} if icon_path else None
        try:
            return self._request("POST", "/project", data={"data": json.dumps(payload)}, files=files, )
        finally:
            if files:
                files["icon"].close()

    def get_project(self, id_or_slug: str) -> DictKV:
        """Fetch a project by ID or slug."""
        return self._request("GET", f"/project/{id_or_slug}")

    def modify_project(self, id_or_slug: str, update: ProjectUpdate) -> None:
        """Modify fields of an existing project (only provided fields will be updated)."""
        payload = {k: v for k, v in update.__dict__.items() if v is not None}
        self._request("PATCH", f"/project/{id_or_slug}", json=payload)

    def change_project_icon(self, id_or_slug: str, icon_path: Path, ext: str) -> None:
        """Change the icon of a project (max 256 KiB)."""
        with icon_path.open("rb") as icon_file:
            self._request("PATCH", f"/project/{id_or_slug}/icon", params={"ext": ext}, data=icon_file)

    def create_version(self, version: NewVersion, file_paths: List[Path], primary_file: Optional[str] = None) -> DictKV:
        """Create a new version for a Modrinth project."""
        files = {}
        try:
            file_parts = []
            for idx, path in enumerate(file_paths):
                part_name = f"file{idx}"
                files[part_name] = path.open("rb")
                file_parts.append(part_name)

            payload: DictKV = {**version.__dict__, "file_parts": file_parts}
            if primary_file:
                payload["primary_file"] = primary_file

            return self._request("POST", "/version", data={"data": json.dumps(payload)}, files=files)
        finally:
            for f in files.values():
                f.close()

    def add_gallery_image(self, id_or_slug: str, image: GalleryImage) -> None:
        """Upload an image to a project's gallery (<= 5 MiB)."""
        params: DictKV = {"ext": image.ext, "featured": str(image.featured).lower(), }
        if image.title:
            params["title"] = image.title
        if image.description:
            params["description"] = image.description
        if image.ordering is not None:
            params["ordering"] = image.ordering

        with image.image_path.open("rb") as img_file:
            self._request("POST", f"/project/{id_or_slug}/gallery", params=params, data=img_file)

    def delete_gallery_image(self, id_or_slug: str, image_url: str) -> None:
        """Delete an image from a project's gallery by its URL."""
        self._request("DELETE", f"/project/{id_or_slug}/gallery", params={"url": image_url})

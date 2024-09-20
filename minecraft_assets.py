import os

import requests




def download_minecraft_client_jar(mc_version: str) -> bool:
    manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    manifest_response = requests.get(manifest_url)

    if manifest_response.status_code != 200:
        print(f"Failed to get version manifest: {manifest_response.status_code} (url: {manifest_url})")
        return False

    version_field = next((v for v in manifest_response.json()["versions"] if v["id"] == mc_version), None)
    if not version_field:
        print(f"Version {mc_version} not found! (url: {manifest_url})")
        return False

    version_url = version_field["url"]
    version_response = requests.get(version_url)

    if version_response.status_code != 200:
        print(f"Failed to get version details: {version_response.status_code} (url: {version_url})")
        return False

    client_url = version_response.json()["downloads"]["client"]["url"]

    download_path = f"build/process/{mc_version}/mc_client.jar"
    os.makedirs(os.path.dirname(download_path), exist_ok=True)
    client_response = requests.get(client_url)

    if client_response.status_code != 200:
        print(f"Failed to download the client.jar: {client_response.status_code} (url: {client_url})")
        return False

    with open(download_path, 'wb') as file:
        file.write(client_response.content)
    print(f"Downloaded Minecraft {mc_version} client.jar to {download_path}")
    return True
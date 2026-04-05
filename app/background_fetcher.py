from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import requests


API_ENDPOINTS = {
    "landscape": "https://api.yppp.net/pc.php?return=json",
    "portrait": "https://api.yppp.net/pe.php?return=json",
}


class BackgroundFetchError(RuntimeError):
    pass


def _guess_extension(image_url: str, content_type: str | None, declared_size: str | None) -> str:
    if declared_size:
        ext = declared_size.lower().strip().lstrip(".")
        if ext:
            return f".{ext}"

    if content_type:
        guess = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guess:
            return guess

    suffix = Path(urlparse(image_url).path).suffix
    if suffix:
        return suffix

    return ".jpg"


def _remove_old_variants(directory: Path, stem: str, keep_name: str) -> None:
    for existing in directory.glob(f"{stem}.*"):
        if existing.name != keep_name and existing.is_file():
            existing.unlink(missing_ok=True)


def _download_one(
    session: requests.Session,
    logger,
    api_url: str,
    output_directory: Path,
    stem: str,
) -> str:
    response = session.get(api_url, timeout=30)
    response.raise_for_status()
    payload = response.json()

    image_url = payload.get("acgurl")
    if payload.get("code") != "200" or not image_url:
        raise BackgroundFetchError(f"背景图 API 返回异常：{payload}")

    image_response = session.get(image_url, timeout=60)
    image_response.raise_for_status()

    extension = _guess_extension(image_url, image_response.headers.get("Content-Type"), payload.get("size"))
    file_name = f"{stem}{extension}"
    output_path = output_directory / file_name
    output_directory.mkdir(parents=True, exist_ok=True)
    _remove_old_variants(output_directory, stem, file_name)
    output_path.write_bytes(image_response.content)

    logger.info("背景图已更新：%s", output_path)
    return f"assets/{file_name}"


def fetch_and_store_backgrounds(dist_directory: Path, logger) -> dict[str, str]:
    output_directory = dist_directory / "assets"
    session = requests.Session()

    landscape = _download_one(
        session=session,
        logger=logger,
        api_url=API_ENDPOINTS["landscape"],
        output_directory=output_directory,
        stem="background-landscape",
    )
    portrait = _download_one(
        session=session,
        logger=logger,
        api_url=API_ENDPOINTS["portrait"],
        output_directory=output_directory,
        stem="background-portrait",
    )

    return {
        "landscape": landscape,
        "portrait": portrait,
    }

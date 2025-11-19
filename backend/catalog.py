"""Helpers to load catalog titles and package assignments from JSON files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


class CatalogConfigError(RuntimeError):
    """Raised when catalog metadata is missing or inconsistent."""


ROOT_DIR = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT_DIR / "catalog"
TITLES_PATH = CATALOG_DIR / "titles.json"
PACKAGES_PATH = CATALOG_DIR / "packages.json"


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:  # pragma: no cover - validated at runtime
        raise CatalogConfigError(f"Missing catalog file: {path.name}") from exc


def get_titles() -> tuple[str, Dict[str, Dict[str, Any]]]:
    """Return the audio base path plus title metadata keyed by ID."""

    data = _load_json(TITLES_PATH)
    titles = data.get("titles") or data.get("AUDIOS")
    if not isinstance(titles, dict):
        raise CatalogConfigError("Invalid titles.json: missing 'titles' map")
    path = data.get("path_audios") or data.get("PATH_AUDIOS") or "/AUDIOS/"
    return path, titles


def get_packages() -> List[Dict[str, Any]]:
    data = _load_json(PACKAGES_PATH)
    packages = data.get("packages")
    if not isinstance(packages, list):
        raise CatalogConfigError("Invalid packages.json: missing 'packages' list")
    return packages


def get_package_definition(package_id: str) -> Dict[str, Any]:
    for package in get_packages():
        if package.get("id") == package_id:
            return package
    raise CatalogConfigError(f"Unknown package id: {package_id}")


def get_free_package_definition() -> Dict[str, Any]:
    for package in get_packages():
        if package.get("is_free"):
            return package
    raise CatalogConfigError("packages.json does not define an is_free package")


def build_catalog_response(package: Dict[str, Any]) -> Dict[str, Any]:
    path, titles = get_titles()
    catalog: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []
    for title_id in package.get("title_ids", []):
        if title_id in titles:
            catalog[title_id] = titles[title_id]
        else:
            missing.append(title_id)
    if missing:
        raise CatalogConfigError(
            f"Package {package.get('id')} references unknown titles: {', '.join(missing)}"
        )
    return {"PATH_AUDIOS": path, "AUDIOS": catalog}


def build_catalog_for_package_id(package_id: str) -> Dict[str, Any]:
    package = get_package_definition(package_id)
    return build_catalog_response(package)


def package_lookup_maps() -> tuple[Dict[str, str], Dict[str, str]]:
    """Return helper dicts keyed by Stripe product/price ids."""

    product_map: Dict[str, str] = {}
    price_map: Dict[str, str] = {}
    for package in get_packages():
        pkg_id = package.get("id")
        product_id = package.get("stripe_product_id")
        price_id = package.get("stripe_price_id")
        if product_id:
            product_map[product_id] = pkg_id
        if price_id:
            price_map[price_id] = pkg_id
    return product_map, price_map


def normalize_package_ids(package_ids: Iterable[str]) -> List[str]:
    seen = []
    for package_id in package_ids:
        if package_id and package_id not in seen:
            seen.append(package_id)
    return seen

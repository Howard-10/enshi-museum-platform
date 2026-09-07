"""Lightweight local visual retrieval for the museum's reference images."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

REFERENCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
COLOR_BINS = 12
TEXTURE_BINS = 8
HASH_SIZE = (9, 8)


def _read_image(source: bytes | Path) -> Image.Image:
    if isinstance(source, Path):
        image = Image.open(source)
    else:
        image = Image.open(BytesIO(source))
    return ImageOps.exif_transpose(image).convert("RGB")


def _normalise(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector / norm if norm else vector


def _image_features(source: bytes | Path) -> tuple[np.ndarray, np.ndarray]:
    image = _read_image(source)
    rgb = np.asarray(image.resize((96, 96)), dtype=np.float32)

    color_features: list[float] = []
    for channel in range(3):
        histogram, _ = np.histogram(rgb[:, :, channel], bins=COLOR_BINS, range=(0, 256))
        color_features.extend((histogram / max(histogram.sum(), 1)).tolist())

    grayscale = np.asarray(image.convert("L").resize((48, 48)), dtype=np.float32)
    gradients = np.concatenate([np.abs(np.diff(grayscale, axis=1)).ravel(), np.abs(np.diff(grayscale, axis=0)).ravel()])
    texture_histogram, _ = np.histogram(gradients, bins=TEXTURE_BINS, range=(0, 256))
    texture_features = texture_histogram / max(texture_histogram.sum(), 1)

    hash_pixels = np.asarray(image.convert("L").resize(HASH_SIZE), dtype=np.float32)
    hash_bits = (hash_pixels[:, 1:] > hash_pixels[:, :-1]).astype(np.uint8).ravel()
    feature = np.asarray(color_features + texture_features.tolist(), dtype=np.float32)
    return _normalise(feature), hash_bits


def _reference_entries(root: Path) -> list[dict[str, str]]:
    if not root.exists():
        return []
    entries: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in REFERENCE_EXTENSIONS:
            continue
        artifact = path.parent.name
        if not artifact or artifact == root.name:
            continue
        entries.append({"artifact": artifact, "source": path.name, "path": str(path)})
    return entries


def _signature(entries: list[dict[str, str]]) -> str:
    digest = hashlib.sha1()
    for entry in entries:
        path = Path(entry["path"])
        stat = path.stat()
        digest.update(f"{path}|{stat.st_mtime_ns}|{stat.st_size}|{entry['artifact']}".encode("utf-8"))
    return digest.hexdigest()


@lru_cache(maxsize=4)
def _build_index(root_text: str, signature: str) -> tuple[list[dict[str, str]], np.ndarray, np.ndarray]:
    entries = _reference_entries(Path(root_text))
    usable: list[dict[str, str]] = []
    features: list[np.ndarray] = []
    hashes: list[np.ndarray] = []
    for entry in entries:
        try:
            feature, image_hash = _image_features(Path(entry["path"]))
        except (OSError, ValueError):
            continue
        usable.append(entry)
        features.append(feature)
        hashes.append(image_hash)
    feature_matrix = np.vstack(features) if features else np.empty((0, COLOR_BINS * 3 + TEXTURE_BINS), dtype=np.float32)
    hash_matrix = np.vstack(hashes) if hashes else np.empty((0, HASH_SIZE[0] * (HASH_SIZE[1] - 1)), dtype=np.uint8)
    return usable, feature_matrix, hash_matrix


def search_similar_images(content: bytes, root: str | Path, *, limit: int = 5) -> list[dict[str, Any]]:
    """Return distinct artifact candidates ranked by local visual similarity."""

    root_path = Path(root)
    entries = _reference_entries(root_path)
    if not entries:
        return []
    usable, features, hashes = _build_index(str(root_path), _signature(entries))
    if not usable:
        return []

    # An uploaded file may be one of the museum's own reference images.  Keep
    # this deterministic path ahead of the approximate handcrafted features:
    # posters and screenshots can otherwise look deceptively similar to an
    # unrelated artifact while still receiving a high cosine score.
    query_digest = hashlib.sha256(content).hexdigest()
    exact_results: list[dict[str, Any]] = []
    exact_seen: set[str] = set()
    for entry in usable:
        try:
            if hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest() != query_digest:
                continue
        except OSError:
            continue
        artifact = entry["artifact"]
        if artifact in exact_seen:
            continue
        exact_seen.add(artifact)
        exact_results.append(
            {
                "artifact": artifact,
                "source": entry["source"],
                "score": 1.0,
                "backend": "local_exact_sha256_v1",
            }
        )
        if len(exact_results) >= limit:
            break
    if exact_results:
        return exact_results

    query_feature, query_hash = _image_features(content)
    feature_scores = features @ query_feature
    hash_scores = 1 - np.mean(hashes != query_hash, axis=1)
    scores = 0.8 * feature_scores + 0.2 * hash_scores
    ranked = np.argsort(-scores)

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in ranked:
        entry = usable[int(row)]
        artifact = entry["artifact"]
        if artifact in seen:
            continue
        seen.add(artifact)
        results.append(
            {
                "artifact": artifact,
                "source": entry["source"],
                "score": round(float(scores[row]), 4),
                "backend": "local_handcrafted_v1",
            }
        )
        if len(results) >= limit:
            break
    return results

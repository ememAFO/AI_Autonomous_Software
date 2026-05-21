from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


class ProtectedFileIntegrityError(Exception):
    pass


@dataclass(frozen=True)
class ProtectedManifest:
    hashes: dict[str, str]


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(project_root: str | Path, protected_dir: str = "protected") -> ProtectedManifest:
    root = Path(project_root).resolve()
    folder = root / protected_dir
    hashes: dict[str, str] = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            hashes[str(path.relative_to(root))] = _hash_file(path)
    return ProtectedManifest(hashes=hashes)


def verify_manifest(project_root: str | Path, manifest: ProtectedManifest) -> None:
    current = build_manifest(project_root)
    if current.hashes != manifest.hashes:
        missing = sorted(set(manifest.hashes) - set(current.hashes))
        added = sorted(set(current.hashes) - set(manifest.hashes))
        changed = sorted(
            key for key in set(current.hashes) & set(manifest.hashes)
            if current.hashes[key] != manifest.hashes[key]
        )
        raise ProtectedFileIntegrityError(
            f"Protected files changed. missing={missing}, added={added}, changed={changed}"
        )

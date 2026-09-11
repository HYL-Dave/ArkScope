"""Market-store-bound capture roots and portable relative object keys."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath


@dataclass(frozen=True)
class SecResearchPaths:
    market_db_path: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "market_db_path", Path(self.market_db_path).resolve())

    @classmethod
    def resolve(cls) -> SecResearchPaths:
        from src.market_data_admin import resolve_market_db_path

        return cls.from_market_db(resolve_market_db_path())

    @classmethod
    def from_market_db(cls, path: str | Path) -> SecResearchPaths:
        return cls(market_db_path=Path(path))

    @property
    def capture_root(self) -> Path:
        path = self.market_db_path
        return path.parent / (path.name + ".sec-research")

    def object_path(self, key: str) -> Path:
        """Resolve a portable relative key without creating directories or files.

        Containment is checked at resolution time; future file I/O must also
        guard against concurrent filesystem changes.
        """
        if not isinstance(key, str) or not key:
            raise ValueError("SEC object key must be a nonempty string")

        relative = PurePosixPath(key)
        windows = PureWindowsPath(key)
        if (
            relative.is_absolute()
            or windows.drive
            or windows.root
            or not relative.parts
            or relative.as_posix() != key
            or ".." in relative.parts
            or any(
                char in '<>:"\\|?*' or ord(char) < 32 or ord(char) == 127
                for char in key
            )
            or any(
                part.endswith((".", " ")) or PureWindowsPath(part).is_reserved()
                for part in relative.parts
            )
        ):
            raise ValueError(
                "SEC object key must be a portable relative path without traversal"
            )

        root = self.capture_root
        try:
            resolved = root.joinpath(*relative.parts).resolve()
        except (OSError, RuntimeError) as exc:
            raise ValueError("SEC object key cannot be resolved safely") from exc
        # Keep the DB-derived root as the anchor, even if that root is a symlink.
        if resolved == root or not resolved.is_relative_to(root):
            raise ValueError("SEC object key escapes the capture root")
        return resolved

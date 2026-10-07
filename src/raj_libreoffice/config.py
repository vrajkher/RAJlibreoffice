from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    workspace: Path
    uno_python: str = "/usr/bin/python3"
    soffice: str = "libreoffice"
    connection: str = ""
    timeout: float = 120
    advanced: bool = False
    scripts: bool = False
    python_execution: bool = False
    max_cells: int = 100000
    max_text: int = 1000000

    @classmethod
    def from_env(cls):
        return cls(
            workspace=Path(os.getenv("RAJ_WORKSPACE", "./workspace")).resolve(),
            uno_python=os.getenv("RAJ_UNO_PYTHON", "/usr/bin/python3"),
            soffice=os.getenv("RAJ_SOFFICE", "libreoffice"),
            connection=os.getenv("RAJ_UNO_CONNECTION", ""),
            timeout=float(os.getenv("RAJ_TIMEOUT", "120")),
            advanced=os.getenv("RAJ_ALLOW_ADVANCED", "0") == "1",
            scripts=os.getenv("RAJ_ALLOW_SCRIPTS", "0") == "1",
            python_execution=os.getenv("RAJ_ALLOW_PYTHON", "0") == "1",
        )

    def wire(self):
        return {**self.__dict__, "workspace": str(self.workspace)}


def workspace_path(root: Path, value: str, *, exists: bool = False) -> Path:
    """Resolve symlinks before checking containment; reject remote and file URLs."""
    if not value or "://" in value or value.startswith("private:"):
        raise ValueError("Use a local path inside RAJ_WORKSPACE, not a URL")
    path = Path(value).expanduser()
    path = (root / path if not path.is_absolute() else path).resolve()
    if path != root and root not in path.parents:
        raise ValueError("Path is outside RAJ_WORKSPACE")
    if exists and not path.is_file():
        raise FileNotFoundError(str(path))
    return path


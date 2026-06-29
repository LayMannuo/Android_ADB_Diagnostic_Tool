from __future__ import annotations

import zipfile
from pathlib import Path


class ZipExporter:
    def export(self, source_dir: Path) -> Path:
        archive = source_dir.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in source_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(source_dir.parent))
        return archive

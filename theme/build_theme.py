"""Package the branchLeft blog Ghost theme into a zip that Ghost can install."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

THEME_DIR: Path = Path(__file__).resolve().parent
DEFAULT_OUT: Path = THEME_DIR / "dist" / "branchleft-blog-theme.zip"

REQUIRED_FILES: tuple[str, ...] = (
    "package.json",
    "default.hbs",
    "index.hbs",
    "post.hbs",
    "page.hbs",
    "assets/css/tokens.css",
    "assets/css/screen.css",
)


def build(theme_dir: Path, out_zip: Path) -> Path:
    """Zip the required theme files, refusing if any is missing."""
    missing = [name for name in REQUIRED_FILES if not (theme_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"theme is missing: {', '.join(missing)}")
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in REQUIRED_FILES:
            archive.write(theme_dir / name, arcname=name)
    return out_zip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    written = build(THEME_DIR, args.out)
    print(f"wrote {written}")


if __name__ == "__main__":
    main()

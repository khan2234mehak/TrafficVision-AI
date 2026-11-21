"""Download YOLO11 weights into backend/models (they are NOT committed to git).

Usage:  python scripts/download_weights.py [model]     e.g. yolo11n.pt (default) | yolo11s.pt | yolo11m.pt
Bigger models are more accurate but slower on CPU. yolo11n is a good start.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "backend" / "models"
URLS = [
    "https://github.com/ultralytics/assets/releases/download/v8.3.0/{name}",
    "https://github.com/ultralytics/assets/releases/latest/download/{name}",
]


def download(name: str) -> bool:
    DEST.mkdir(parents=True, exist_ok=True)
    target = DEST / name
    if target.exists() and target.stat().st_size > 1_000_000:
        print(f"[ok] {target} already exists")
        return True
    for tpl in URLS:
        url = tpl.format(name=name)
        try:
            print(f"Downloading {url}")
            tmp = target.with_suffix(".part")
            with urllib.request.urlopen(url, timeout=60) as r, tmp.open("wb") as f:
                total = int(r.headers.get("Content-Length", 0))
                done = 0
                while chunk := r.read(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r  {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
            print()
            if tmp.stat().st_size < 1_000_000:
                raise RuntimeError("downloaded file is too small")
            tmp.replace(target)
            print(f"[ok] saved to {target}")
            return True
        except Exception as e:  # noqa: BLE001
            print(f"  failed: {e}")
    # last resort: let Ultralytics fetch it
    try:
        from ultralytics import YOLO
        import shutil, os
        cwd = os.getcwd()
        os.chdir(DEST)
        try:
            YOLO(name)
        finally:
            os.chdir(cwd)
        if target.exists():
            print(f"[ok] saved to {target}")
            return True
    except Exception as e:  # noqa: BLE001
        print(f"  ultralytics fallback failed: {e}")
    print(f"\n[error] Could not download {name}. Download it manually from https://github.com/ultralytics/assets/releases "
          f"and place it in {DEST}")
    return False


if __name__ == "__main__":
    sys.exit(0 if download(sys.argv[1] if len(sys.argv) > 1 else "yolo11n.pt") else 1)

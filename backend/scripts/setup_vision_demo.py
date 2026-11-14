"""Install the pinned official YOLO11 nano weights for local object-detection demos."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from urllib.request import urlopen


URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt"
SHA256 = "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"
DESTINATION = Path(__file__).resolve().parents[1] / "vision_models" / "yolo11n.pt"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> None:
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if DESTINATION.exists() and digest(DESTINATION) == SHA256:
        print(f"Verified existing demo weights: {DESTINATION}")
        return
    with tempfile.NamedTemporaryFile(dir=DESTINATION.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            with urlopen(URL, timeout=30) as response:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    temporary.write(chunk)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
    if digest(temporary_path) != SHA256:
        temporary_path.unlink(missing_ok=True)
        raise ValueError("Downloaded YOLO weights failed SHA-256 verification")
    temporary_path.replace(DESTINATION)
    print(f"Installed verified demo weights: {DESTINATION}")


if __name__ == "__main__":
    main()

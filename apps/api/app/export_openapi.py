from __future__ import annotations

import json
from pathlib import Path

from .main import app


def main() -> None:
    target = Path(__file__).parents[3] / "packages" / "api-types" / "openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

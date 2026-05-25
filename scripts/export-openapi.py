from pathlib import Path
import json

from app.main import create_app


def main() -> None:
    output = Path("frontend/lib/openapi.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

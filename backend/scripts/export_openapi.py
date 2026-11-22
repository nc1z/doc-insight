"""Write the API schema to stdout so the frontend can regenerate its types."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.main import create_app


def main() -> None:
    application = create_app(
        Settings(_env_file=None, llm_provider="mock", classifier_provider="mock")
    )
    json.dump(application.openapi(), sys.stdout)


if __name__ == "__main__":
    main()

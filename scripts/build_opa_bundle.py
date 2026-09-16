import json
import os
from pathlib import Path

BUNDLE_DIR = Path("opa/bundle")
MANIFEST_PATH = BUNDLE_DIR / ".manifest"
DATA_PATH = BUNDLE_DIR / "data.json"


def main() -> None:
    revision = os.environ.get("POLICY_REVISION")
    version = os.environ.get("POLICY_VERSION", "development")

    if not revision:
        raise RuntimeError("POLICY_REVISION is required.")

    manifest = {
        "revision": revision,
    }

    data = {
        "policy_metadata": {
            "bundle_name": "ai-it-support-authz",
            "version": version,
            "revision": revision,
        }
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    DATA_PATH.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

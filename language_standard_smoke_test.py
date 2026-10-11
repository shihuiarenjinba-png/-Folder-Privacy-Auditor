from __future__ import annotations

import json
import os
import tempfile

import language_standard as language


def main() -> None:
    old_local = os.environ.get("LOCALAPPDATA")
    old_override = os.environ.get("PRIVATE_AUTOMATION_UI_LANGUAGE")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["LOCALAPPDATA"] = temp_dir
            os.environ.pop("PRIVATE_AUTOMATION_UI_LANGUAGE", None)
            app_id = "language-smoke"
            language._save(app_id, "ja")
            assert language._load(app_id) == "ja"
            assert json.loads(language._path(app_id).read_text(encoding="utf-8")) == {"language": "ja"}
            language._save(app_id, "en")
            assert language._load(app_id) == "en"
            os.environ["PRIVATE_AUTOMATION_UI_LANGUAGE"] = "ja"
            assert language._load(app_id) == "ja"
            try:
                language._save(app_id, "fr")
            except ValueError:
                pass
            else:
                raise AssertionError("unsupported language must be rejected")
    finally:
        if old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = old_local
        if old_override is None:
            os.environ.pop("PRIVATE_AUTOMATION_UI_LANGUAGE", None)
        else:
            os.environ["PRIVATE_AUTOMATION_UI_LANGUAGE"] = old_override
    print("language standard smoke test: OK")


if __name__ == "__main__":
    main()

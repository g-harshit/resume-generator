"""Write the JSON Schema the TypeScript types are generated from.

uv run python -m app.schemas.export   (or `pnpm gen:schema` from the repo root)
"""

import json
from pathlib import Path

from app.schemas.resume import ResumeData

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "packages/schema/resume.schema.json"


def _drop_titles(node):
    if isinstance(node, dict):
        # A string "title" is an annotation; a dict "title" is a field called title
        # (Experience.title) and must stay.
        return {
            k: _drop_titles(v) for k, v in node.items() if not (k == "title" and isinstance(v, str))
        }
    if isinstance(node, list):
        return [_drop_titles(v) for v in node]
    return node


def current_schema() -> str:
    # Pydantic titles every field ("Start", "Date"…) and json2ts turns each title into
    # its own exported type alias, one of them shadowing the global `Date`. So drop
    # all titles, then give back only the models' own names.
    schema = ResumeData.model_json_schema(mode="serialization")
    clean = _drop_titles(schema)
    clean["title"] = schema["title"]
    for name, definition in schema["$defs"].items():
        clean["$defs"][name]["title"] = definition["title"]
    return json.dumps(clean, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    SCHEMA_PATH.write_text(current_schema())
    print(f"wrote {SCHEMA_PATH}")

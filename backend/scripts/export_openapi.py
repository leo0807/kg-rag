#!/usr/bin/env python3
"""Export FastAPI OpenAPI spec to JSON without starting the server."""
import json
import os
import sys

# Ensure imports resolve correctly when run from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch env so Settings validates without real DB
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")

from src.main import app  # noqa: E402

spec = app.openapi()
out = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(spec, f, ensure_ascii=False, indent=2)
print(f"OpenAPI spec exported to {out} ({len(spec['paths'])} paths)")

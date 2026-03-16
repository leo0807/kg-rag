#!/bin/bash
export PYTHONPATH=""
export PATH="/Users/scott/Desktop/kg-rag/backend/.venv/bin:$PATH"
python -m uvicorn src.main:app --port 8000 --loop asyncio

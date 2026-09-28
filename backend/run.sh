#!/usr/bin/env bash
# Activates the venv and starts the FastAPI dev server in one step.
cd "$(dirname "$0")"
source .venv/bin/activate
uvicorn main:app --reload --port 8000

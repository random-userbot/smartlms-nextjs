#!/bin/bash
# Azure Launch Script for Smart LMS Backend
# Using Gunicorn for production performance (better than raw uvicorn)

echo "Starting SmartLMS Backend on Azure..."
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

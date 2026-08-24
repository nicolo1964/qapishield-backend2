#!/bin/bash

# QAPIShield Backend Start Script
# This script initializes the database and starts the FastAPI server

echo "🚀 Starting QAPIShield Backend..."

# Run database migrations
echo "📊 Running database migrations..."
alembic upgrade head

# Start the FastAPI server
echo "🌐 Starting FastAPI server..."
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'

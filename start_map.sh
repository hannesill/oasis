#!/bin/bash
# Simple script to start the OASIS map server

echo "🌴 Starting OASIS Map Server..."
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    echo "   Create .env with: MAPBOX_TOKEN=pk.ey..."
    echo ""
fi

# Start the server
python map_api.py


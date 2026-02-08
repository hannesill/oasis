#!/bin/bash
# Start OASIS Map with public ngrok tunnel

echo "🌴 Starting OASIS Map Server..."
echo ""

# Check if server is already running
if pgrep -f "map_api.py" > /dev/null; then
    echo "✅ Map server already running"
else
    echo "🚀 Starting map server..."
    python map_api.py &
    sleep 2
fi

# Check if ngrok is already running
if pgrep -f "ngrok http 8000" > /dev/null; then
    echo "✅ ngrok tunnel already running"
    echo ""
    echo "📋 Getting public URL..."
    sleep 2
    PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); tunnels = data.get('tunnels', []); print(tunnels[0]['public_url'] if tunnels else '')" 2>/dev/null)
    if [ -n "$PUBLIC_URL" ]; then
        echo "🌐 Public URL: $PUBLIC_URL"
    else
        echo "⚠️  Could not get ngrok URL. Check http://localhost:4040"
    fi
else
    echo "🌐 Starting ngrok tunnel..."
    ngrok http 8000 --log=stdout > /tmp/ngrok.log 2>&1 &
    sleep 3
    
    echo ""
    echo "📋 Getting public URL..."
    PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); tunnels = data.get('tunnels', []); print(tunnels[0]['public_url'] if tunnels else '')" 2>/dev/null)
    
    if [ -n "$PUBLIC_URL" ]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ OASIS Map is now publicly accessible!"
        echo ""
        echo "🌐 Public URL: $PUBLIC_URL"
        echo "📊 ngrok Dashboard: http://localhost:4040"
        echo "🏠 Local URL: http://localhost:8000"
        echo ""
        echo "💡 Share the public URL with anyone to access the map!"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    else
        echo "⚠️  ngrok started but URL not available yet."
        echo "   Check http://localhost:4040 for the public URL"
    fi
fi

echo ""
echo "Press Ctrl+C to stop (or run: pkill -f ngrok; pkill -f map_api.py)"


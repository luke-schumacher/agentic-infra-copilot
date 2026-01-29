#!/bin/bash
# ============================================================
# Agentic Infra Co-Pilot - Quick Start Script (Mac/Linux)
# ============================================================

echo ""
echo "============================================================"
echo "   Agentic Infra Co-Pilot - Docker Startup"
echo "============================================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found!"
    echo ""
    echo "Please create a .env file with your GROQ_API_KEY:"
    echo "  1. Copy .env.example to .env"
    echo "  2. Add your Groq API key from https://console.groq.com"
    echo ""
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running!"
    echo "Please start Docker and try again."
    exit 1
fi

echo "Starting all services with Docker Compose..."
echo ""

# Build and start
docker-compose up --build -d

echo ""
echo "============================================================"
echo "   Services Starting..."
echo "============================================================"
echo ""
echo "   Neo4j Browser:    http://localhost:7474"
echo "   Telekom Minister: http://localhost:8001"
echo "   Siemens Tech:     http://localhost:8002"
echo "   Illigo Operator:  http://localhost:8003"
echo "   Streamlit UI:     http://localhost:8501"
echo ""
echo "============================================================"
echo ""
echo "Waiting for services to be healthy (this may take 1-2 minutes)..."
echo ""

# Wait for services
sleep 30

echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop:      docker-compose down"
echo ""

# Open browser (works on Mac)
if command -v open &> /dev/null; then
    open http://localhost:8501
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8501
fi

echo "Streamlit UI should open in your browser at http://localhost:8501"

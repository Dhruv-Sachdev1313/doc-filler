#!/bin/bash

# Build and run script for Document Filler application

echo "🐳 Building Document Filler Docker image..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Build the image
echo "📦 Building Docker image..."
docker build -t doc-filler . || {
    echo "❌ Failed to build Docker image"
    exit 1
}

echo "✅ Docker image built successfully!"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env file and add your GEMINI_API_KEY"
    echo "   Then run: docker run -p 8000:8000 --env-file .env doc-filler"
else
    echo "🚀 Starting container..."
    # Kill any existing containers using port 8000
    docker stop $(docker ps -q --filter "publish=8000") 2>/dev/null || true
    
    # Run the container
    docker run -d -p 8000:8000 --env-file .env --name doc-filler-app doc-filler
    
    if [ $? -eq 0 ]; then
        echo "✅ Container started successfully!"
        echo "🌐 Application is running at: http://localhost:8000"
        echo "📊 View logs: docker logs doc-filler-app"
        echo "🛑 Stop container: docker stop doc-filler-app"
    else
        echo "❌ Failed to start container"
        exit 1
    fi
fi
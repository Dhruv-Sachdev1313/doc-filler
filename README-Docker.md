# Document Filler - Docker Deployment

This application is containerized using Docker for easy deployment.

## Prerequisites

1. Docker installed on your system
2. Gemini API key from Google AI Studio

## Quick Start

### 1. Clone and Setup
```bash
git clone <your-repo-url>
cd llm-docs-filler
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 2. Build and Run with Docker Compose
```bash
# For development (with hot reload)
docker-compose up --build

# For production
docker-compose --profile production up --build app-prod
```

### 3. Or build manually
```bash
# Build the image
docker build -t doc-filler .

# Run the container
docker run -p 8000:8000 -e GEMINI_API_KEY=your_api_key_here doc-filler
```

## Access the Application

Open your browser and navigate to: `http://localhost:8000`

## Environment Variables

- `GEMINI_API_KEY`: Your Google Gemini AI API key (required)

## Docker Commands

### Build Image
```bash
docker build -t doc-filler .
```

### Run Container
```bash
docker run -p 8000:8000 --env-file .env doc-filler
```

### Stop Container
```bash
docker stop <container_id>
```

### View Logs
```bash
docker logs <container_id>
```

### Remove Container and Image
```bash
docker rm <container_id>
docker rmi doc-filler
```

## Development

For development with hot reload:
```bash
docker-compose up
```

This mounts the local directory into the container so changes are reflected immediately.

## Production Deployment

For production deployment:
```bash
docker-compose --profile production up -d app-prod
```

## Health Check

The container includes a health check that verifies the application is running properly. You can check the health status:

```bash
docker ps
```

Look for the health status in the STATUS column.

## Troubleshooting

### Port Already in Use
If port 8000 is already in use:
```bash
# Kill processes using port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
docker run -p 3000:8000 --env-file .env doc-filler
```

### Container Won't Start
1. Check logs: `docker logs <container_id>`
2. Verify environment variables are set correctly
3. Ensure Docker daemon is running

### API Key Issues
1. Verify your Gemini API key is correct
2. Check if the API key has proper permissions
3. Ensure the `.env` file is properly formatted

## Security Notes

- The application runs as a non-root user inside the container
- Environment variables should be kept secure
- For production, consider using Docker secrets or a secret management system
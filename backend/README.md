# CAMRAIL RailMind Lite - Backend

## Deployment with Docker Compose

To run the full backend environment (API + PostgreSQL), make sure you have Docker Desktop installed. 

> [!NOTE]
> **Ollama (Local LLM)** is NOT containerized in this setup to maintain maximum GPU performance. It must be running directly on your host machine (Windows/Mac). The API container connects to it via `host.docker.internal:11434`. (For Linux hosts, you might need to add `extra_hosts` to the docker-compose file).

### Steps to Run:

1. Build and start the containers in detached mode:
   ```bash
   docker compose up -d
   ```

2. Check the API logs to ensure it started successfully and ran the database migrations:
   ```bash
   docker compose logs -f api
   ```

3. The API is now available at `http://localhost:8000`. You can access the automatic documentation at `http://localhost:8000/docs`.

4. The database is automatically seeded on startup with default users and security groups.

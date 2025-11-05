# 🤖 AI Thought Processor

An AI agent that captures thoughts from Telegram messages (text & voice), transcribes them using a speech-to-text AI, and then uses an LLM (Google Gemini) to intelligently analyze and organize them in a Notion database.

## ✨ Key Features

*   **Telegram Integration:** Fetches new messages from a Telegram bot at regular intervals (polling).
*   **Voice Transcription:** Voice messages are automatically converted to text using Gladia AI.
*   **Intelligent Processing:** Google Gemini analyzes the collected texts, understands the context, consolidates ideas, and derives actions (e.g., create a new task, update an existing one).
*   **Retrieval Augmented Generation (RAG):** Leverages a local vector database (FAISS with HuggingFace embeddings) to provide the LLM with relevant context from existing Notion pages, improving decision-making for creating, updating, or archiving entries.
*   **Notion Synchronization:** Creates or updates entries in a Notion database based on the LLM's analysis.
*   **Containerized:** The entire project is packaged in Docker for simple, isolated, and reproducible execution.

## 🏛️ Architecture & Project Structure

The project follows a modular, service-oriented approach. Each external API (Telegram, Gladia, Notion, Gemini) has its own dedicated service in `/app/services`. The `workflow_processor.py` orchestrates these services to control the entire flow.

```
.
├── app/
│   ├── main.py                 # Initializes logging and starts the hybrid runtime
│   ├── bootstrap.py            # Orchestrates polling catch-up + webhook startup
│   ├── config.py               # Loads and validates all env configuration
│   ├── logging_config.py       # Configures application-wide logging
│   ├── cache_model.py          # Caches the embedding model during Docker build
│   ├── services/               # Modules for external APIs
│   │   ├── telegram_service.py
│   │   ├── gladia_service.py
│   │   ├── notion_service.py
│   │   ├── llm_service.py
│   │   └── vector_service.py   # Handles vector index creation and querying for RAG
│   ├── processing/
│   │   └── workflow_processor.py # The main workflow orchestrator
│   └── webhook_api.py          # FastAPI app for webhook + health endpoints
├── prompts/
│   ├── gemini_prompt.md
│   └── thought_structuring_prompt.md
├── scripts/
│   ├── entrypoint.sh           # Container entrypoint that prepares state & launches the app
│   └── inspect_security_logs.py # Helper to audit webhook-related logs
├── (.env)                      # Your secret API keys (to be created!)
├── .env.example                # Template for the .env file
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Build instructions for the application image
└── docker-compose.yml          # Service definition for Docker Compose
```

## 🛠️ Setup

### 1. Prerequisites

Docker and Docker Compose must be installed on your system. The container image bundles every required Python dependency (langchain-huggingface, sentence-transformers, faiss-cpu, torch, etc.), so you do not need to install them locally.

You will need API keys for the following services:

*   **Telegram:** Create a bot with `@BotFather` and copy the token.
*   **Gladia AI:** Create an account at Gladia AI and get your API key.
*   **Google AI Studio:** Create an API key for Gemini in Google AI Studio.
*   **Notion:** Create a Notion Integration and copy the "Internal Integration Secret" token.

### 2. Configuration

Clone the repository:
```bash
git clone git@github.com:maximilian-armuss-dev/telegram2notion.git
cd telegram2notion
```

Create the `.env` file: Copy the template and fill in your API keys and the Notion Database ID.
```bash
cp .env.example .env
```
Now, open the `.env` file and set your credentials and runtime options:

- **Core tokens:** `TELEGRAM_BOT_TOKEN`, `GLADIA_API_KEY`, `GOOGLE_API_KEY`, `NOTION_API_KEY`, `NOTION_DATABASE_ID`.
- **Webhook:** `WEBHOOK_URL`, `WEBHOOK_SECRET_TOKEN` (must match the Cloudflare gateway), and optionally `WEBHOOK_HOST/PORT`.
- **Network allowlist:** Replace the placeholder values in `TELEGRAM_ALLOWED_CIDRS` with the latest ranges from the [Telegram documentation](https://core.telegram.org/bots/webhooks#the-short-answer).
- **Other tuning:** Adjust Gladia rate limits, RAG depth, timezone, or container UID/GID as needed.

Make sure any reverse proxy or Cloudflare tunnel forwards traffic to the same origin port specified via `WEBHOOK_PORT`, so that external ingress matches the running FastAPI server (default `8000`).
When operating behind the companion Cloudflare tunnel, set `WEBHOOK_SECRET_TOKEN` in `.env` to the same value as `TELEGRAM_SECRET` in the tunnel repository; both sides must share the exact secret or the gateway will return HTTP 403.
You can generate a suitably long secret (256 hex characters) with:
```bash
openssl rand -hex 128
```
If you want the container to run as a specific host user or group, adjust `SERVICE_UID` and `SERVICE_GID` in `.env` (defaults: `1000`).

Set up the Notion Database:

*   Create a new database in Notion.
*   Click the three dots (...) in the top-right corner of the database -> "Add connection" and select the integration you created earlier.
*   The Database ID is the part of the URL between your workspace name and the question mark.  Example: `https://www.notion.so/DATABASE_ID?v=...`

## 🚀 Running the Application

### Starting the Application

Build and start the Docker container in detached mode:
```bash
docker compose up --build -d
```
The application is now running. The FastAPI server exposes a readiness endpoint at `http://localhost:8000/health` and serves the OpenAPI docs at `/docs`. The webhook listener is automatically registered with Telegram when `WEBHOOK_ENABLED=true`.

> ℹ️ Wenn du Änderungen an Python-Abhängigkeiten oder am Dockerfile vorgenommen hast (z. B. aktualisierte HuggingFace-Caching-Logik), rebuild das Image vor dem Start explizit:
> ```bash
> docker compose build --no-cache
> docker compose up -d
> ```

### Manual Trigger

You can access the interactive API documentation at `http://localhost:8000/docs` (or update the port to match your `WEBHOOK_PORT`) and invoke the `/run-workflow` endpoint manually if you need to trigger processing without waiting for new Telegram messages.

## 🔍 Operations & Observability

- **Webhook health check:** `GET /health` returns `{"status": "ok"}` when the FastAPI server is ready.
- **Security log audit:** Run `python scripts/inspect_security_logs.py --since 12h` to filter container logs for rejected webhook attempts (missing/invalid secret, disallowed IPs, bad content types, etc.). Use `--container` if your Docker engine names the container differently.
- **Docker healthcheck:** The compose file continuously probes the `/health` endpoint to ensure the service stays responsive; review `docker compose ps` for status.

Once the container is running and the webhook is configured, the hybrid runtime keeps watching for Telegram updates—no cron job is required. Polling is only used during startup to drain any backlog before switching to the webhook stream.

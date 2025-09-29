# 🤖 AI Thought Processor

An AI agent that captures thoughts from Telegram messages (text & voice), transcribes them using a speech-to-text AI, and then uses an LLM (Google Gemini) to intelligently analyze and organize them in a Notion database.

## ✨ Key Features

*   **Telegram Integration:** Fetches new messages from a Telegram bot at regular intervals (polling).
*   **Voice Transcription:** Voice messages are automatically converted to text using Gladia AI.
*   **Intelligent Processing:** Google Gemini analyzes the collected texts, understands the context, consolidates ideas, and derives actions (e.g., create a new task, update an existing one).
*   **Notion Synchronization:** Creates or updates entries in a Notion database based on the LLM's analysis.
*   **Containerized:** The entire project is packaged in Docker for simple, isolated, and reproducible execution.

## 🏛️ Architecture & Project Structure

The project follows a modular, service-oriented approach. Each external API (Telegram, Gladia, Notion, Gemini) has its own dedicated service in `/app/services`. The `workflow_processor.py` orchestrates these services to control the entire flow.

```
.
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI endpoint and main script
│   ├── config.py               # Loads all settings from .env
│   ├── logging_config.py       # Configures application-wide logging
│   ├── services/               # Modules for external APIs
│   │   ├── telegram_service.py
│   │   ├── gladia_service.py
│   │   ├── notion_service.py
│   │   └── llm_service.py
│   └── processing/
│       └── workflow_processor.py # The main workflow orchestrator
├── prompts/
│   └── main_prompt.txt         # The master prompt for the LLM
├── (.env)                      # Your secret API keys (to be created!)
├── .env.example                # Template for the .env file
├── .cursorrules                # AI coding assistant rules
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Instructions for building the Docker image
├── docker-compose.yml          # Service definition for Docker Compose
├── entrypoint.sh               # Initialization script
├── ai-agent-cron               # Crontab file defining time interval between executions
```

## 🛠️ Setup

### 1. Prerequisites

Docker and Docker Compose must be installed on your system.

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
Now, open the `.env` file and enter your values.

Set up the Notion Database:

*   Create a new database in Notion.
*   Click the three dots (...) in the top-right corner of the database -> "Add connection" and select the integration you created earlier.
*   The Database ID is the part of the URL between your workspace name and the question mark.  Example: `https://www.notion.so/DATABASE_ID?v=...`

## 🚀 Running the Application

### Starting the Application

Build and start the Docker container in detached mode:
```bash
docker-compose up --build -d
```
The application is now running. The FastAPI server is available on port 8000 if you wish to trigger the workflow manually.

### Manual Trigger

You can access the interactive API documentation at `http://localhost:8000/docs` and execute the `/run-workflow` endpoint manually.

### Automated Execution (Cron Job)

The workflow will run once on startup and then every 10 minutes as defined in the `ai-agent-cron` file.
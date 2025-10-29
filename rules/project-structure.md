# 🤖 KI-Entwicklungsrichtlinien (Projekt-Spezifisch) 🤖

---

## 1. Projektübersicht & Architektur

Bevor du arbeitest, mache dich mit dem Projekt vertraut.

### 1.1. High-Level-Ziel

Dieses Projekt ist ein asynchroner Python-Agent, der Nachrichten (Text und Sprache) aus einem Telegram-Chat extrahiert, sie mittels eines LLM und RAG in strukturierte Notion-Datenbankeinträge umwandelt und diese über die Notion-API synchronisiert.

### 1.2. Verzeichnisstruktur & Verantwortlichkeiten

Die gesamte Anwendungslogik befindet sich im Verzeichnis `/app`.

```
/
├── app/
│   ├── processing/
│   │   └── workflow_processor.py   # 💡 HERZSTÜCK: Orchestriert den gesamten Workflow
│   ├── services/
│   │   ├── telegram_service.py     # Kapselt die Telegram Bot API
│   │   ├── gladia_service.py       # Kapselt die Gladia Speech-to-Text API
│   │   ├── llm_service.py          # Kapselt die Interaktion mit dem LLM (LangChain)
│   │   ├── notion_service.py       # Kapselt die Notion API
│   │   └── vector_service.py       # Verwaltet die Vektor-Datenbank für RAG
│   ├── config.py                   # ✅ Zentrales Laden der .env-Konfiguration
│   ├── logging_config.py           # Konfiguration für das Logging-Modul
│   ├── main.py                     # 🚀 Haupteinstiegspunkt der Anwendung
│   ├── models.py                   # Pydantic-Datenmodelle für Notion-Strukturen
│   └── state_manager.py            # Verwaltet den Zustand (verarbeitete Nachrichten)
├── prompts/                        # Speichert LLM-Prompts als .md-Dateien
├── .env                            # Speichert alle Secrets und Konfigurationen und darf nie gelesen werden
├── .env.example                    # Beispiel für eine .env Datei, darf gelesen werden
└── ...
```

### 1.3. Kern-Workflow (End-to-End)

1.  **Start:** `main.py` ruft den `WorkflowProcessor` in `workflow_processor.py` auf.
2.  **Setup:** Der Prozessor initialisiert alle Services und baut den RAG-Vektorindex auf.
3.  **Fetch:** Neue Nachrichten werden von Telegram geholt.
4.  **Content Extraction:** Text wird direkt verwendet; Sprachnachrichten werden transkribiert.
5.  **RAG Context:** Relevante Dokumente werden über den `VectorService` aus Notion geholt.
6.  **LLM Processing:** Der `LLMService` generiert aus den Gedanken und dem Kontext eine Liste von validierten Notion-Aktionen.
7.  **Execution:** Der `NotionService` führt diese Aktionen aus (create, update, archive).
8.  **State Update:** Die IDs der verarbeiteten Nachrichten werden gespeichert.

---

## 2. Architekturprinzipien

-   **Separation of Concerns:** Halte die Verantwortlichkeiten strikt getrennt. `workflow_processor.py` orchestriert nur. Die gesamte Logik für externe APIs (Telegram, Notion, Gladia) gehört ausschließlich in die entsprechenden Service-Klassen in `/app/services`.
-   **Keine Hartcodierung:** Alle Konfigurationswerte, API-Keys, Dateipfade, Modellnamen oder "magische" Strings müssen aus der `.env`-Datei über das `settings`-Objekt aus `app/config.py` geladen werden.
-   **Logging über `print()`:** Die `print()`-Funktion ist verboten. Verwende für jegliche Ausgabe das `logging`-Modul (`logging.info`, `logging.error`).
-   **SDKs bevorzugen:** Nutze immer die offiziellen SDKs (`python-telegram-bot`, `notion-client`), anstatt direkte HTTP-Anfragen mit `httpx` oder `requests` zu implementieren.

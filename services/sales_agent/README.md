# Sales Agent Service

Stateful Vietnamese sales agent built with Google ADK. The service separates
order validation, agent configuration, ADK runtime/session management, and HTTP
transport.

```bash
uvicorn services.sales_agent.main:app --reload --port 8002
```

Set `GOOGLE_API_KEY` for the primary Gemini model. The default fallback uses
Groq and requires `GROQ_API_KEY`. Only quota exhaustion activates fallback;
other primary failures return a service error for visibility.

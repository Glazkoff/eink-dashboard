# E-Ink Dashboard Skill

Generate and display e-ink dashboards with real-time data from providers.

## What it does

- Fetches data from context providers (weather, calendar, tasks, news, time)
- Calls eink-dashboard API to generate visual dashboard
- Sends result to eink_mcp for display

## Quick Start

```
@Sanya show my morning dashboard
@Sanya display weather for Moscow
@Sanya show calendar and tasks
```

## Configuration

Set in your `.env`:

```bash
EINK_DASHBOARD_URL=http://localhost:8080
EINK_MCP_URL=http://localhost:5000

# Optional: Default providers to use
EINK_DEFAULT_PROVIDERS=weather,calendar,tasks,time
```

## Skills

### `/show-dashboard`

Generate and display an e-ink dashboard.

```bash
User: @Sanya show my morning dashboard
```

Behavior:
1. Fetches data from all default providers
2. Builds context with fetched data
3. Calls eink-dashboard `/learn` endpoint
4. Sends result to eink_mcp

### `/weather`

Show weather dashboard.

```bash
User: @Sanya show weather for Moscow
```

### `/calendar`

Show calendar and tasks dashboard.

```bash
User: @Sanya show what's on my schedule today
```

### `/news`

Show news headlines dashboard.

```bash
User: @Sanya show me the latest tech news
```

### `/time`

Show time/date dashboard.

```bash
User: @Sanya what's the time
```

## Implementation

```python
# skills/eink_dashboard.py
import os
import httpx
from context_providers import fetch_contexts

EINK_DASHBOARD_URL = os.getenv("EINK_DASHBOARD_URL", "http://localhost:8080")
DEFAULT_PROVIDERS = os.getenv("EINK_DEFAULT_PROVIDERS", "weather,time").split(",")

async def show_dashboard(prompt: str = "Daily dashboard", providers: list[str] = None):
    """Generate and display e-ink dashboard."""
    providers = providers or DEFAULT_PROVIDERS
    
    # Fetch data from providers
    contexts = await fetch_contexts(providers)
    
    # Call eink-dashboard
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{EINK_DASHBOARD_URL}/learn",
            json={
                "prompt": prompt,
                "context": contexts,
                "context_providers": providers,
                "duration": 120,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()
```

## Context Data Structure

```python
# Example data sent to eink-dashboard
{
    "weather": {
        "temperature": 22,
        "condition": "Sunny",
        "humidity": 65,
        "forecast": [...]
    },
    "calendar": {
        "events": [
            {"time": "10:00", "title": "Meeting", "duration": 30},
            ...
        ],
        "date": "Friday, March 20"
    },
    "tasks": {
        "items": [
            {"title": "Review PR", "priority": "high"},
            ...
        ],
        "count": 3
    },
    "time": {
        "time": "14:30",
        "date": "2026-03-20",
        "weekday": "Friday"
    },
    "news": {
        "headlines": [
            {"title": "AI Breakthrough", "source": "TechCrunch"},
            ...
        ],
        "updated": "14:25"
    }
}
```

## E-Ink Dashboard Response

```json
{
  "success": true,
  "image_url": "/images/dashboard_abc123.png",
  "template_id": "weather_calendar_7f3a",
  "template_is_new": false,
  "critic_score": 0.85,
  "critic_verdict": "approve",
  "attempts": 1,
  "result": {
    "id": 42,
    "status": "pending"
  }
}
```

## Advanced Usage

### Custom Providers

```bash
User: @Sanya show dashboard with weather and tasks
User: @Sanya generate dashboard for London
```

### Template Selection

```bash
User: @Sanya show weather with dark template
```

### Specific Duration

```bash
User: @Sanya display this for 5 minutes
```

## Troubleshooting

### eink-dashboard not responding

```bash
# Check if eink-dashboard server is running
curl http://localhost:8080/health

# Should return: {"status": "ok"}
```

### eink_mcp not receiving

```bash
# Check eink_mcp status
curl http://localhost:5000/api/status

# Verify content plan
curl http://localhost:5000/api/plan
```

## Integration Notes

This skill works with:

- **OpenClaw** - Add to `skills/` directory
- **NanoClaw** - Add to `skills/` directory (same format)
- **Direct Python** - Import and use directly

The skill uses:
- `context_providers.py` - Fetch data from various sources
- `eink-dashboard` HTTP API - Generate dashboards
- `eink_mcp` HTTP API - Display on e-ink screen

## Related Projects

- [eink-dashboard](https://github.com/Glazkoff/eink-dashboard) - Dashboard generator
- [eink_mcp](https://github.com/Glazkoff/eink_mcp) - E-ink display MCP server
- [OpenClaw](https://github.com/openclaw/openclaw) - AI agent framework
- [NanoClaw](https://github.com/qwibitai/nanoclaw) - Lightweight AI agent

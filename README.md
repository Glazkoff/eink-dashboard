# E-Ink Dashboard Generator

AI-powered HTML dashboard generator for e-ink displays. Generates dashboards via LLM (OpenRouter/Z.ai), renders to 800x480, validates with VLM critic, and sends to eink_mcp content plan.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Prompt    │ ──▶ │  LLM (OpenRouter │ ──▶ │    HTML     │
│  / Context  │     │     / Z.ai)      │     │  Dashboard  │
└─────────────┘     └──────────────────┘     └─────────────┘
                                                   │
                                                   ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  eink_mcp   │ ◀── │   VLM Critic     │ ◀── │  Playwright │
│    Plan     │     │   (validate)     │     │   Render    │
└─────────────┘     └──────────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Approve   │ → Send to eink_mcp
                    │   Retry     │ → Regenerate with feedback
                    │   Abort     │ → Skip, notify user
                    └─────────────┘
```

## Features

- **LLM Dashboard Generation** - OpenRouter/Z.ai compatible APIs
- **VLM Quality Critic** - Validates rendered images before sending
- **Auto-Retry with Feedback** - Critic feedback improves regeneration
- **HTML → PNG Rendering** - Playwright headless browser (800x480)
- **E-Ink Optimized** - Tri-color palette support (black/red/white)
- **Template System** - Reusable dashboard templates
- **CLI + API** - Use from command line or integrate programmatically

## Installation

```bash
# Clone
git clone https://github.com/Glazkoff/eink-dashboard.git
cd eink-dashboard

# Create venv
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Configure
cp .env.example .env
# Edit .env with your API keys
```

## Configuration

```bash
# .env
OPENAI_API_KEY=your_key_here           # Or OpenRouter API key
OPENAI_BASE_URL=https://openrouter.ai/api/v1  # Optional, for OpenRouter
OPENAI_MODEL=openai/gpt-4o-mini        # Model for generation

EINK_MCP_URL=http://localhost:5000     # eink_mcp Web UI URL
OUTPUT_DIR=./output                    # Where to save generated images
```

## Usage

### CLI

```bash
# Generate dashboard from prompt
python generate.py --prompt "Show weather, calendar events, and a quote of the day"

# Use specific template
python generate.py --template weather --prompt "Moscow weather"

# Send to eink_mcp plan
python generate.py --prompt "Daily summary" --send --duration 60

# With VLM critic validation
python generate.py --prompt "Daily summary" --critic --send

# With critic + custom settings
python generate.py \
  --prompt "Show my calendar" \
  --critic \
  --critic-model openai/gpt-4o \
  --threshold 0.8 \
  --max-retries 3 \
  --send

# Custom context (inject data)
python generate.py --context data.json --prompt "Render this data as a dashboard"
```

### VLM Critic

The critic evaluates rendered images on 5 criteria:

| Criterion | Weight | Checks |
|-----------|--------|--------|
| **Layout Integrity** | 25% | Alignment, bounds, spacing |
| **Text Readability** | 30% | Font size, contrast, overlap |
| **Color Correctness** | 20% | Only black/red/white, no gradients |
| **Content Accuracy** | 15% | Matches intent, clear presentation |
| **E-Ink Optimization** | 10% | Clean edges, efficient palette use |

**Verdicts:**
- `approve` (score ≥ 0.7) - Send to eink_mcp
- `retry` (score 0.4-0.69) - Regenerate with feedback
- `abort` (score < 0.4) - Skip generation, notify

```bash
# CLI with critic
python generate.py --prompt "Weather dashboard" --critic --send

# Adjust threshold
python generate.py --prompt "Stats" --critic --threshold 0.8 --send

# Max retries before giving up
python generate.py --prompt "Schedule" --critic --max-retries 5 --send
```

### Python API

```python
from generator import DashboardGenerator
from critic import DashboardCritic, CriticVerdict

gen = DashboardGenerator()
critic = DashboardCritic(threshold_approve=0.7)

# Generate HTML
html = await gen.generate_html("Show my daily stats")

# Render to image
image_path = await gen.render(html)

# Evaluate with critic
result = await critic.evaluate(image_path, prompt="Show my daily stats")

print(f"Score: {result.score}")
print(f"Verdict: {result.verdict.value}")
print(f"Issues: {result.issues}")

if result.verdict == CriticVerdict.APPROVE:
    # Send to eink_mcp
    await gen.send_to_plan(image_path, duration=60)
elif result.verdict == CriticVerdict.RETRY:
    # Get feedback for regeneration
    feedback = critic.get_feedback_prompt(result)
    new_html = await gen.generate_html(f"Show my daily stats\n\n{feedback}")
    # ... retry loop
```

## Templates

Built-in templates in `templates/`:

- `minimal.html` - Clean base with e-ink optimized styles
- `weather.html` - Weather display layout
- `stats.html` - Statistics/metrics grid
- `schedule.html` - Calendar/events list

Templates use `{{ variables }}` for dynamic content.

## E-Ink Optimization

Generated images are optimized for tri-color e-ink:

- Color quantization to black/red/white palette
- High contrast text
- No gradients (solid colors only)
- 800x480 resolution

## API Endpoints (Server Mode)

```bash
# Run as HTTP server
python server.py --port 8080
```

Endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/generate` | POST | Generate HTML dashboard |
| `/render` | POST | Render HTML to PNG |
| `/send` | POST | Send image to eink_mcp |
| `/critic` | POST | Evaluate image with VLM critic |
| `/generate-and-send` | POST | Full pipeline (no critic) |
| `/generate-with-critic` | POST | Full pipeline with critic validation |
| `/templates` | GET | List available templates |
| `/images/{filename}` | GET | Serve generated image |
| `/health` | GET | Health check |

### Example: Generate with Critic

```bash
curl -X POST http://localhost:8080/generate-with-critic \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Show weather forecast for Moscow",
    "template": "weather",
    "duration": 120,
    "threshold": 0.75,
    "max_retries": 3
  }'
```

Response:
```json
{
  "success": true,
  "image_path": "/app/output/dashboard_abc123.png",
  "image_url": "/images/dashboard_abc123.png",
  "critic_score": 0.85,
  "critic_verdict": "approve",
  "attempts": 1,
  "result": {"id": 42, "status": "pending"}
}
```

## Related Projects

- [eink_mcp](https://github.com/Glazkoff/eink_mcp) - E-ink display MCP server
- [OpenRouter](https://openrouter.ai) - LLM API gateway
- [Z.ai](https://z.ai) - LLM API provider

## License

MIT

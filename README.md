# E-Ink Dashboard Generator

AI-powered HTML dashboard generator for e-ink displays with **VLM critic validation** and **template learning system**. Generates dashboards via LLM, validates quality, learns from successful outputs, and sends to eink_mcp content plan.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Prompt    │ ──▶ │  LLM (OpenRouter │ ──▶ │    HTML     │
│  / Context  │     │     / Z.ai)      │     │  Dashboard  │
└─────────────┘     └──────────────────┘     └─────────────┘
         │                                          │
         │                                          ▼
         │     ┌──────────────────┐     ┌─────────────┐
         │     │   VLM Critic     │ ◀── │  Playwright │
         │     │   (validate)     │     │   Render    │
         │     └────────┬─────────┘     └─────────────┘
         │              │
         │              ▼
         │     ┌─────────────────┐
         │     │    Approve      │──────▶ Send to eink_mcp
         │     │    Retry        │──────▶ Regenerate with feedback
         │     │    Abort        │──────▶ Use best or fail
         │     └─────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    TEMPLATE LEARNING                         │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │   Prompt     │───▶│  Classify    │───▶│  Match       │   │
│  │              │    │  Intent      │    │  Template    │   │
│  └──────────────┘    └──────────────┘    └──────┬───────┘   │
                                                   │          │
                        ┌──────────────────────────┼───┐      │
                        │                          │   │      │
                        ▼                          ▼   │      │
                   ┌─────────┐                ┌─────────┐│      │
                   │ Reuse   │                │ Create  ││      │
                   │Template │                │  New    ││      │
                   └────┬────┘                └────┬────┘│      │
                        │                          │     │      │
                        └──────────┬───────────────┘     │      │
                                   ▼                     │      │
                          ┌────────────────┐             │      │
                          │    Generate    │             │      │
                          │    Dashboard   │◀────────────┘      │
                          └───────┬────────┘                    │
                                  │                             │
                                  ▼                             │
                          ┌────────────────┐                    │
                          │ Critic Result  │                    │
                          │ (success/fail) │                    │
                          └───────┬────────┘                    │
                                  │                             │
                                  ▼                             │
                          ┌────────────────┐                    │
                          │ Update Stats   │────────────────────┘
                          │ (learn)        │
                          └────────────────┘
└─────────────────────────────────────────────────────────────┘
```

## Features

- **LLM Dashboard Generation** - OpenRouter/Z.ai compatible APIs
- **VLM Quality Critic** - Validates rendered images before sending
- **Auto-Retry with Feedback** - Critic feedback improves regeneration
- **Template Learning** - Creates and reuses successful templates
- **Intent Classification** - Matches prompts to best template
- **HTML → PNG Rendering** - Playwright headless browser (800x480)
- **E-Ink Optimized** - Tri-color palette support (black/red/white)
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
# Basic generation
python generate.py --prompt "Show weather, calendar events, and a quote of the day"

# With template learning (recommended)
python generate.py --prompt "Show weather for Moscow today and tomorrow" --learn --critic --send

# With built-in template
python generate.py --template weather --prompt "Moscow weather"

# With VLM critic validation
python generate.py --prompt "Daily summary" --critic --send

# Full pipeline: learning + critic + send
python generate.py \
  --prompt "Weather forecast for the week" \
  --learn \
  --critic \
  --threshold 0.75 \
  --max-retries 3 \
  --send \
  --duration 120

# List learned templates
python generate.py --list-templates
```

### Template Learning

The system automatically:
1. **Classifies** your prompt (intent, keywords, complexity)
2. **Matches** against existing learned templates
3. **Reuses** successful templates if confidence ≥ threshold
4. **Creates** new templates when no match found
5. **Records** results to improve future matching

**How it works:**
- First time you ask "Show weather today and tomorrow" → creates new template
- Next time you ask "Weather forecast for Moscow" → reuses template (high confidence)
- Template success rate affects future matching
- Failed generations decrease template priority

```bash
# Enable learning
python generate.py --prompt "Show my calendar" --learn --critic --send

# Adjust confidence threshold
python generate.py --prompt "Stats dashboard" --learn --min-confidence 0.8 --send
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
from template_registry import TemplateRegistry

# With template learning
gen = DashboardGenerator(use_template_learning=True)
critic = DashboardCritic(threshold_approve=0.7)

# Generate with learning
html, template_id, is_new = await gen.generate_with_template_learning(
    "Show weather for Moscow today and tomorrow"
)

# Render to image
image_path = await gen.render(html)

# Evaluate with critic
result = await critic.evaluate(image_path, prompt="Show weather...")

print(f"Score: {result.score}")
print(f"Verdict: {result.verdict.value}")

if result.verdict == CriticVerdict.APPROVE:
    # Record success for learning
    gen.record_template_result(template_id, success=True, score=result.score, prompt="...")
    # Send to eink_mcp
    await gen.send_to_plan(image_path, duration=60)
```

## Templates

Built-in templates in `templates/`:

- `minimal.html` - Clean base with e-ink optimized styles
- `weather.html` - Weather display layout
- `stats.html` - Statistics/metrics grid
- `schedule.html` - Calendar/events list

Learned templates stored in `templates/learned/` with metadata in `output/template_registry.json`.

## API Endpoints (Server Mode)

```bash
# Run as HTTP server
python server.py --port 8080
```

Then open **http://localhost:8080** in your browser for the **Web UI**!

### Web UI Features

- **Generate dashboards** - Enter prompt, configure options
- **Template learning** - Enable/disable with checkbox
- **VLM critic** - Validate quality before sending  
- **Preview** - See rendered image at 800x480
- **Template browser** - View built-in and learned templates
- **One-click send** - Send to eink_mcp after generation

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/generate` | POST | Generate HTML dashboard |
| `/render` | POST | Render HTML to PNG |
| `/send` | POST | Send image to eink_mcp |
| `/critic` | POST | Evaluate image with VLM critic |
| `/generate-and-send` | POST | Full pipeline (no critic) |
| `/generate-with-critic` | POST | Full pipeline with critic |
| `/learn` | POST | Full pipeline with template learning + critic |
| `/record` | POST | Manually record template result |
| `/templates` | GET | List built-in templates |
| `/templates/learned` | GET | List learned templates with stats |
| `/templates/{id}` | GET | Get specific template |
| `/images/{filename}` | GET | Serve generated image |
| `/health` | GET | Health check |

### Example: Generate with Learning

```bash
curl -X POST http://localhost:8080/learn \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Show weather forecast for Moscow today and tomorrow",
    "duration": 120,
    "min_confidence": 0.7,
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
  "template_id": "weather_7f3a2b",
  "template_is_new": false,
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

# E-Ink Dashboard Generator

AI-powered HTML dashboard generator for e-ink displays. Generates dashboards via LLM (OpenRouter/Z.ai), renders to 800x480, and sends to eink_mcp content plan.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Prompt    │ ──▶ │  LLM (OpenRouter │ ──▶ │    HTML     │
│  / Context  │     │     / Z.ai)      │     │  Dashboard  │
└─────────────┘     └──────────────────┘     └─────────────┘
                                                   │
                                                   ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  eink_mcp   │ ◀── │   POST /api/plan │ ◀── │  Playwright │
│    Plan     │     │   (image path)   │     │   Render    │
└─────────────┘     └──────────────────┘     └─────────────┘
```

## Features

- **LLM Dashboard Generation** - OpenRouter/Z.ai compatible APIs
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
OPENAI_MODEL=openai/gpt-4o-mini        # Model to use

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

# Custom context (inject data)
python generate.py --context data.json --prompt "Render this data as a dashboard"
```

### Python API

```python
from generator import DashboardGenerator

gen = DashboardGenerator()

# Generate HTML
html = await gen.generate_html("Show my daily stats")

# Render to image
image_path = await gen.render(html)

# Send to eink_mcp
await gen.send_to_plan(image_path, duration=60, template="image_only")
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

## API Endpoints (Optional Server Mode)

```bash
# Run as HTTP server
python server.py --port 8080
```

Endpoints:

- `POST /generate` - Generate dashboard from prompt
- `POST /render` - Render HTML to image
- `POST /send` - Send to eink_mcp plan

## Related Projects

- [eink_mcp](https://github.com/Glazkoff/eink_mcp) - E-ink display MCP server
- [OpenRouter](https://openrouter.ai) - LLM API gateway
- [Z.ai](https://z.ai) - LLM API provider

## License

MIT

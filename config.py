"""Configuration for E-Ink Dashboard Generator."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "output"))
TEMPLATES_DIR = BASE_DIR / "templates"

# Display settings
DISPLAY_WIDTH = int(os.getenv("DISPLAY_WIDTH", 800))
DISPLAY_HEIGHT = int(os.getenv("DISPLAY_HEIGHT", 480))

# LLM API settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")  # None = OpenAI default
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")

# eink_mcp settings
EINK_MCP_URL = os.getenv("EINK_MCP_URL", "http://localhost:5000")

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

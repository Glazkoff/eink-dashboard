"""Dashboard generator core logic."""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from openai import AsyncOpenAI
from playwright.async_api import async_playwright

from config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    OUTPUT_DIR,
    TEMPLATES_DIR,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    EINK_MCP_URL,
)


class DashboardGenerator:
    """Generate HTML dashboards via LLM and render to images."""

    SYSTEM_PROMPT = """You are an e-ink dashboard generator. Generate clean, minimal HTML dashboards optimized for 800x480 tri-color e-ink displays (black, red, white only).

Rules:
- Use ONLY black (#000), red (#c00), and white (#fff) colors
- High contrast, large readable fonts
- No gradients, shadows, or transparency
- Simple layouts that work at 800x480
- Use system fonts: Arial, Helvetica, sans-serif
- No external CSS/JS, everything inline
- Responsive to 800x480 viewport
- Maximum simplicity - e-ink refreshes are slow

Generate complete HTML documents with embedded CSS.
Focus on clarity over decoration."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
        )

    async def generate_html(
        self,
        prompt: str,
        context: Optional[dict] = None,
        template: Optional[str] = None,
    ) -> str:
        """Generate HTML dashboard from prompt using LLM."""
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
        ]

        # Add context if provided
        if context:
            context_str = f"Context data:\n{json.dumps(context, indent=2, ensure_ascii=False)}"
            messages.append({"role": "user", "content": context_str})

        # Add template if provided
        if template:
            template_path = TEMPLATES_DIR / f"{template}.html"
            if template_path.exists():
                template_html = template_path.read_text()
                prompt = f"Base template:\n```html\n{template_html}\n```\n\n{prompt}"

        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=4000,
        )

        content = response.choices[0].message.content

        # Extract HTML from markdown code block if present
        if "```html" in content:
            content = content.split("```html")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        return content

    async def render(
        self,
        html: str,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Render HTML to PNG image using Playwright."""
        if output_path is None:
            # Generate unique filename
            hash_input = html + datetime.now().isoformat()
            filename = hashlib.md5(hash_input.encode()).hexdigest()[:12]
            output_path = OUTPUT_DIR / f"dashboard_{filename}.png"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                viewport={"width": DISPLAY_WIDTH, "height": DISPLAY_HEIGHT},
                device_scale_factor=1,
            )

            await page.set_content(html, wait_until="networkidle")
            await page.screenshot(path=str(output_path), type="png")

            await browser.close()

        return output_path

    async def send_to_plan(
        self,
        image_path: Path,
        duration: int = 60,
        template: str = "image_only",
        priority: int = 0,
    ) -> dict:
        """Send image to eink_mcp content plan."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{EINK_MCP_URL}/api/plan",
                json={
                    "type": "image",
                    "content": str(image_path.absolute()),
                    "duration": duration,
                    "template": template,
                    "priority": priority,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def generate_and_send(
        self,
        prompt: str,
        context: Optional[dict] = None,
        template: Optional[str] = None,
        duration: int = 60,
        priority: int = 0,
    ) -> tuple[Path, dict]:
        """Full pipeline: generate HTML, render, and send to plan."""
        html = await self.generate_html(prompt, context, template)
        image_path = await self.render(html)
        result = await self.send_to_plan(image_path, duration, priority)
        return image_path, result

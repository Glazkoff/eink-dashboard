"""Template registry with learning and reuse."""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_BASE_URL, TEMPLATES_DIR, OUTPUT_DIR

# Built-in templates directory
BUILTIN_TEMPLATES = TEMPLATES_DIR


@dataclass
class TemplateMeta:
    """Metadata for a learned template."""
    id: str
    name: str
    description: str
    tags: list[str]
    created_at: str
    uses: int
    successes: int
    avg_score: float
    last_used: Optional[str] = None
    example_prompts: list[str] = None

    def __post_init__(self):
        if self.example_prompts is None:
            self.example_prompts = []

    @property
    def success_rate(self) -> float:
        if self.uses == 0:
            return 0.0
        return self.successes / self.uses

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TemplateMeta":
        return cls(**data)


class TemplateRegistry:
    """Manages template storage, selection, and learning."""

    TEMPLATE_CLASSIFIER_PROMPT = """Analyze this dashboard generation prompt and classify it.

Prompt: "{prompt}"

Respond in JSON format:
```json
{
  "intent": "weather|schedule|stats|quote|calendar|mixed|other",
  "keywords": ["keyword1", "keyword2"],
  "complexity": "simple|medium|complex",
  "suggested_layout": "single|split|grid|list",
  "data_types": ["text", "numbers", "time", "image"],
  "description": "Brief description of what this template should show"
}
```"""

    TEMPLATE_MATCH_PROMPT = """Given a prompt and available templates, select the best match or indicate if a new template is needed.

Prompt: "{prompt}"

Available templates:
{templates}

Respond in JSON:
```json
{
  "best_match": "template_id or null",
  "confidence": 0.0-1.0,
  "reason": "Why this template fits or doesn't fit",
  "needs_new_template": true/false
}
```

Select existing template if confidence >= 0.7. Otherwise, indicate a new template is needed."""

    TEMPLATE_GENERATOR_PROMPT = """Create an HTML template for an e-ink dashboard (800x480, black/red/white only).

Requirements:
- Intent: {intent}
- Keywords: {keywords}
- Complexity: {complexity}
- Layout: {layout}
- Data types: {data_types}
- Description: {description}

Create a template with {{variable}} placeholders for dynamic content.
Use inline CSS only. Only black (#000), red (#c00), and white (#fff) colors.
High contrast, large readable fonts, no gradients.

Output the complete HTML template."""

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or (OUTPUT_DIR / "template_registry.json")
        self.templates_dir = TEMPLATES_DIR / "learned"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        self._registry: dict[str, TemplateMeta] = {}
        self._load_registry()

    def _load_registry(self):
        """Load registry from disk."""
        if self.registry_path.exists():
            data = json.loads(self.registry_path.read_text())
            self._registry = {
                k: TemplateMeta.from_dict(v) for k, v in data.items()
            }

    def _save_registry(self):
        """Save registry to disk."""
        data = {k: v.to_dict() for k, v in self._registry.items()}
        self.registry_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _generate_template_id(self, intent: str, keywords: list[str]) -> str:
        """Generate unique template ID."""
        content = f"{intent}_{'_'.join(sorted(keywords[:3]))}"
        return hashlib.md5(content.encode()).hexdigest()[:8]

    async def classify_prompt(self, prompt: str) -> dict:
        """Classify a prompt to understand its intent."""
        response = await self.client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "user", "content": self.TEMPLATE_CLASSIFIER_PROMPT.format(prompt=prompt)}
            ],
            temperature=0.3,
            max_tokens=500,
        )

        content = response.choices[0].message.content

        # Extract JSON
        import re
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
        if json_match:
            return json.loads(json_match.group(1))
        return json.loads(re.search(r"\{[\s\S]*\}", content).group(0))

    async def find_best_template(self, prompt: str, classification: dict) -> tuple[Optional[str], float, bool]:
        """Find the best matching template for a prompt."""
        if not self._registry:
            return None, 0.0, True

        # Build template list for matching
        templates_info = []
        for tid, meta in self._registry.items():
            templates_info.append(
                f"- {tid}: {meta.name} ({meta.description}) "
                f"[tags: {', '.join(meta.tags)}] "
                f"[success_rate: {meta.success_rate:.0%}]"
            )

        templates_str = "\n".join(templates_info)

        response = await self.client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": self.TEMPLATE_MATCH_PROMPT.format(
                        prompt=prompt,
                        templates=templates_str
                    )
                }
            ],
            temperature=0.2,
            max_tokens=300,
        )

        content = response.choices[0].message.content

        # Parse response
        import re
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
        if json_match:
            data = json.loads(json_match.group(1))
        else:
            data = json.loads(re.search(r"\{[\s\S]*\}", content).group(0))

        best_match = data.get("best_match")
        confidence = data.get("confidence", 0.0)
        needs_new = data.get("needs_new_template", confidence < 0.7)

        return best_match, confidence, needs_new

    async def create_template(self, prompt: str, classification: dict) -> tuple[str, str]:
        """Create a new template based on classification."""
        template_id = self._generate_template_id(
            classification["intent"],
            classification["keywords"]
        )

        # Generate HTML template
        response = await self.client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": self.TEMPLATE_GENERATOR_PROMPT.format(
                        intent=classification["intent"],
                        keywords=", ".join(classification["keywords"]),
                        complexity=classification["complexity"],
                        layout=classification["suggested_layout"],
                        data_types=", ".join(classification["data_types"]),
                        description=classification["description"],
                    )
                }
            ],
            temperature=0.5,
            max_tokens=3000,
        )

        html = response.choices[0].message.content

        # Extract HTML from code block if present
        import re
        if "```html" in html:
            html = html.split("```html")[1].split("```")[0].strip()
        elif "```" in html:
            html = html.split("```")[1].split("```")[0].strip()

        # Save template file
        template_path = self.templates_dir / f"{template_id}.html"
        template_path.write_text(html)

        # Create metadata
        template_name = f"{classification['intent']}_{template_id}"
        meta = TemplateMeta(
            id=template_id,
            name=template_name,
            description=classification["description"],
            tags=classification["keywords"] + [classification["intent"]],
            created_at=datetime.now().isoformat(),
            uses=0,
            successes=0,
            avg_score=0.0,
            example_prompts=[prompt],
        )

        self._registry[template_id] = meta
        self._save_registry()

        return template_id, html

    def get_template(self, template_id: str) -> Optional[str]:
        """Load template HTML by ID."""
        # Check learned templates first
        template_path = self.templates_dir / f"{template_id}.html"
        if template_path.exists():
            return template_path.read_text()

        # Check built-in templates
        builtin_path = TEMPLATES_DIR / f"{template_id}.html"
        if builtin_path.exists():
            return builtin_path.read_text()

        return None

    def record_use(self, template_id: str, success: bool, score: float, prompt: str):
        """Record a template usage result."""
        if template_id not in self._registry:
            return

        meta = self._registry[template_id]
        meta.uses += 1
        meta.last_used = datetime.now().isoformat()

        if success:
            meta.successes += 1

        # Update average score
        total_score = meta.avg_score * (meta.uses - 1) + score
        meta.avg_score = total_score / meta.uses

        # Add example prompt (keep last 10)
        if prompt not in meta.example_prompts:
            meta.example_prompts.append(prompt)
            meta.example_prompts = meta.example_prompts[-10:]

        self._save_registry()

    async def get_or_create_template(
        self,
        prompt: str,
        min_confidence: float = 0.7,
    ) -> tuple[str, str, bool]:
        """Get best matching template or create new one.

        Returns: (template_id, template_html, is_new)
        """
        # Classify the prompt
        classification = await self.classify_prompt(prompt)

        # Try to find existing template
        template_id, confidence, needs_new = await self.find_best_template(
            prompt, classification
        )

        # Use existing if confident enough
        if not needs_new and template_id and confidence >= min_confidence:
            html = self.get_template(template_id)
            if html:
                return template_id, html, False

        # Create new template
        template_id, html = await self.create_template(prompt, classification)
        return template_id, html, True

    def list_templates(self) -> list[TemplateMeta]:
        """List all templates sorted by success rate."""
        return sorted(
            self._registry.values(),
            key=lambda t: t.success_rate,
            reverse=True
        )

    def get_template(self, template_id: str) -> Optional[str]:
        """Load template HTML by ID."""
        # Check learned templates first
        template_path = self.templates_dir / f"{template_id}.html"
        if template_path.exists():
            return template_path.read_text()

        # Check built-in templates
        builtin_path = TEMPLATES_DIR / f"{template_id}.html"
        if builtin_path.exists():
            return builtin_path.read_text()

        return None

    def get_stats(self) -> dict:
        """Get registry statistics."""
        if not self._registry:
            return {
                "total_templates": 0,
                "total_uses": 0,
                "avg_success_rate": 0.0,
                "top_templates": [],
            }

        templates = list(self._registry.values())
        return {
            "total_templates": len(templates),
            "total_uses": sum(t.uses for t in templates),
            "avg_success_rate": sum(t.success_rate for t in templates) / len(templates),
            "top_templates": [
                {"id": t.id, "name": t.name, "success_rate": t.success_rate, "uses": t.uses}
                for t in self.list_templates()[:5]
            ],
        }

    def get_template_meta(self, template_id: str) -> Optional[TemplateMeta]:
        """Get template metadata by ID."""
        return self._registry.get(template_id)

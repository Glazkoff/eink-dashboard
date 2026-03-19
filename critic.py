"""VLM-based critic for validating generated dashboards."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI
import base64

from config import OPENAI_API_KEY, OPENAI_BASE_URL, DISPLAY_WIDTH, DISPLAY_HEIGHT


class CriticVerdict(Enum):
    APPROVE = "approve"
    RETRY = "retry"
    ABORT = "abort"


@dataclass
class CriticResult:
    verdict: CriticVerdict
    score: float  # 0.0 - 1.0
    issues: list[str]
    suggestions: list[str]
    raw_response: str


CRITIC_PROMPT = """You are a quality critic for e-ink display dashboards. Analyze this 800x480 PNG image that will be displayed on a tri-color e-ink screen (black, red, white only).

Evaluate the image on these criteria:

1. **LAYOUT INTEGRITY** (weight: 25%)
   - Is content properly aligned and not cut off?
   - Are elements within the 800x480 bounds?
   - Is spacing balanced?

2. **TEXT READABILITY** (weight: 30%)
   - Is text large enough to read on e-ink?
   - Is there sufficient contrast (black on white or red on white)?
   - Is there any text overlap or collision?

3. **COLOR CORRECTNESS** (weight: 20%)
   - Are only black (#000), red (#c00), and white (#fff) used?
   - No grayscale, gradients, or other colors?
   - High contrast between elements?

4. **CONTENT ACCURACY** (weight: 15%)
   - Does the content match the intended dashboard type?
   - Is information clearly presented?
   - No garbled or broken text?

5. **E-INK OPTIMIZATION** (weight: 10%)
   - Clean edges (e-ink doesn't handle fine details well)?
   - No subtle gradients or shadows?
   - Efficient use of limited color palette?

Respond in this EXACT JSON format:
```json
{
  "score": 0.85,
  "verdict": "approve",
  "issues": ["List of problems found, empty if none"],
  "suggestions": ["How to fix issues, empty if perfect"],
  "breakdown": {
    "layout": {"score": 0.9, "notes": "..."},
    "readability": {"score": 0.8, "notes": "..."},
    "colors": {"score": 1.0, "notes": "..."},
    "content": {"score": 0.8, "notes": "..."},
    "optimization": {"score": 0.9, "notes": "..."}
  }
}
```

Verdict options:
- "approve" - Image is good enough for e-ink display (score >= 0.7)
- "retry" - Fixable issues, should regenerate with feedback (score 0.4-0.69)
- "abort" - Fundamental problems, skip this generation (score < 0.4)

Be strict but fair. E-ink displays have limitations and not every design needs to be perfect."""


class DashboardCritic:
    """VLM-based critic for validating e-ink dashboard images."""

    def __init__(
        self,
        model: str = "openai/gpt-4o-mini",  # Vision-capable model
        threshold_approve: float = 0.7,
        threshold_retry: float = 0.4,
    ):
        self.client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
        )
        self.model = model
        self.threshold_approve = threshold_approve
        self.threshold_retry = threshold_retry

    async def evaluate(
        self,
        image_path: Path,
        prompt: Optional[str] = None,
        template: Optional[str] = None,
    ) -> CriticResult:
        """Evaluate a rendered dashboard image."""
        # Read and encode image
        image_data = image_path.read_bytes()
        base64_image = base64.b64encode(image_data).decode("utf-8")

        # Build message with context
        user_content = [
            {
                "type": "text",
                "text": CRITIC_PROMPT,
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}",
                    "detail": "high",
                },
            },
        ]

        # Add context if available
        context_parts = []
        if prompt:
            context_parts.append(f"Original prompt: {prompt}")
        if template:
            context_parts.append(f"Template used: {template}")
        if context_parts:
            user_content.insert(1, {
                "type": "text",
                "text": "\n".join(context_parts),
            })

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": user_content},
            ],
            max_tokens=1000,
            temperature=0.3,
        )

        raw_response = response.choices[0].message.content

        # Parse JSON from response
        result = self._parse_response(raw_response)

        return result

    def _parse_response(self, raw_response: str) -> CriticResult:
        """Parse VLM response into structured result."""
        import json
        import re

        # Extract JSON from response
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", raw_response)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON directly
            json_match = re.search(r"\{[\s\S]*\}", raw_response)
            json_str = json_match.group(0) if json_match else "{}"

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback if parsing fails
            return CriticResult(
                verdict=CriticVerdict.RETRY,
                score=0.5,
                issues=["Failed to parse critic response"],
                suggestions=["Regenerate with simpler design"],
                raw_response=raw_response,
            )

        score = float(data.get("score", 0.5))
        verdict_str = data.get("verdict", "retry")

        # Map verdict
        if verdict_str == "approve" or score >= self.threshold_approve:
            verdict = CriticVerdict.APPROVE
        elif verdict_str == "abort" or score < self.threshold_retry:
            verdict = CriticVerdict.ABORT
        else:
            verdict = CriticVerdict.RETRY

        return CriticResult(
            verdict=verdict,
            score=score,
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            raw_response=raw_response,
        )

    def get_feedback_prompt(self, result: CriticResult) -> str:
        """Generate feedback prompt for retry based on critic result."""
        if result.verdict == CriticVerdict.APPROVE:
            return ""

        feedback_parts = [
            "Previous attempt had issues. Please fix:",
        ]

        for issue in result.issues:
            feedback_parts.append(f"- {issue}")

        if result.suggestions:
            feedback_parts.append("\nSuggestions:")
            for suggestion in result.suggestions:
                feedback_parts.append(f"- {suggestion}")

        feedback_parts.append(f"\nOverall score was: {result.score:.2f}/1.0")
        feedback_parts.append("Generate an improved version addressing these issues.")

        return "\n".join(feedback_parts)

#!/usr/bin/env python3
"""HTTP server for E-Ink Dashboard Generator."""
import asyncio
import json
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from generator import DashboardGenerator
from critic import DashboardCritic, CriticVerdict
from config import OUTPUT_DIR, EINK_MCP_URL

app = FastAPI(title="E-Ink Dashboard Generator API")
gen = DashboardGenerator()
critic = DashboardCritic()


class GenerateRequest(BaseModel):
    prompt: str
    context: Optional[dict] = None
    template: Optional[str] = None


class RenderRequest(BaseModel):
    html: str
    output_path: Optional[str] = None


class SendRequest(BaseModel):
    image_path: str
    duration: int = 60
    template: str = "image_only"
    priority: int = 0


class FullRequest(BaseModel):
    prompt: str
    context: Optional[dict] = None
    template: Optional[str] = None
    duration: int = 60
    priority: int = 0


class CriticRequest(BaseModel):
    image_path: str
    prompt: Optional[str] = None
    template: Optional[str] = None


class FullWithCriticRequest(BaseModel):
    prompt: str
    context: Optional[dict] = None
    template: Optional[str] = None
    duration: int = 60
    priority: int = 0
    max_retries: int = 3
    threshold: float = 0.7


@app.post("/generate")
async def generate(req: GenerateRequest):
    """Generate HTML dashboard from prompt."""
    html = await gen.generate_html(req.prompt, req.context, req.template)
    return {"html": html}


@app.post("/render")
async def render(req: RenderRequest):
    """Render HTML to PNG image."""
    output = Path(req.output_path) if req.output_path else None
    image_path = await gen.render(req.html, output)
    return {"image_path": str(image_path), "image_url": f"/images/{image_path.name}"}


@app.post("/send")
async def send(req: SendRequest):
    """Send image to eink_mcp content plan."""
    try:
        result = await gen.send_to_plan(
            Path(req.image_path),
            duration=req.duration,
            template=req.template,
            priority=req.priority,
        )
        return {"success": True, "result": result}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"eink_mcp error: {e}")


@app.post("/generate-and-send")
async def generate_and_send(req: FullRequest, background_tasks: BackgroundTasks):
    """Full pipeline: generate, render, and send to plan."""
    try:
        image_path, result = await gen.generate_and_send(
            prompt=req.prompt,
            context=req.context,
            template=req.template,
            duration=req.duration,
            priority=req.priority,
        )
        return {
            "success": True,
            "image_path": str(image_path),
            "result": result,
        }
    except httpx.HTTPError as e:
        raise HTTPException(502, f"eink_mcp error: {e}")


@app.post("/critic")
async def evaluate_with_critic(req: CriticRequest):
    """Evaluate an image with the VLM critic."""
    image_path = Path(req.image_path)
    if not image_path.exists():
        raise HTTPException(404, "Image not found")

    result = await critic.evaluate(
        image_path,
        prompt=req.prompt,
        template=req.template,
    )

    return {
        "verdict": result.verdict.value,
        "score": result.score,
        "issues": result.issues,
        "suggestions": result.suggestions,
    }


@app.post("/generate-with-critic")
async def generate_with_critic(req: FullWithCriticRequest):
    """Full pipeline with critic: generate, evaluate, retry if needed, send."""
    # Configure critic with custom threshold
    custom_critic = DashboardCritic(threshold_approve=req.threshold)

    current_prompt = req.prompt
    attempt = 0
    best_result = None
    best_score = 0
    best_image = None

    while attempt <= req.max_retries:
        attempt += 1

        # Generate HTML
        html = await gen.generate_html(current_prompt, req.context, req.template)

        # Render to image
        image_path = await gen.render(html)

        # Evaluate with critic
        result = await custom_critic.evaluate(
            image_path,
            prompt=req.prompt,
            template=req.template,
        )

        # Track best attempt
        if result.score > best_score:
            best_score = result.score
            best_result = result
            best_image = image_path

        # Check verdict
        if result.verdict == CriticVerdict.APPROVE:
            break

        if result.verdict == CriticVerdict.ABORT:
            if best_score >= 0.5:
                # Use best attempt instead of failing
                image_path = best_image
                result = best_result
                break
            raise HTTPException(422, {
                "error": "Critic aborted generation",
                "issues": result.issues,
                "attempts": attempt,
            })

        # Prepare feedback for retry
        if attempt <= req.max_retries:
            feedback = custom_critic.get_feedback_prompt(result)
            current_prompt = f"{req.prompt}\n\n{feedback}"

    # Send to eink_mcp
    try:
        send_result = await gen.send_to_plan(
            best_image or image_path,
            duration=req.duration,
            priority=req.priority,
        )
    except httpx.HTTPError as e:
        raise HTTPException(502, f"eink_mcp error: {e}")

    return {
        "success": True,
        "image_path": str(best_image or image_path),
        "image_url": f"/images/{(best_image or image_path).name}",
        "critic_score": best_score,
        "critic_verdict": (best_result or result).verdict.value,
        "attempts": attempt,
        "result": send_result,
    }


@app.get("/images/{filename}")
async def get_image(filename: str):
    """Serve generated images."""
    image_path = OUTPUT_DIR / filename
    if not image_path.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(image_path, media_type="image/png")


@app.get("/templates")
async def list_templates():
    """List available templates."""
    from config import TEMPLATES_DIR
    templates = [f.stem for f in TEMPLATES_DIR.glob("*.html")]
    return {"templates": templates}


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

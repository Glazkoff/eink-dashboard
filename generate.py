#!/usr/bin/env python3
"""CLI for E-Ink Dashboard Generator."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from generator import DashboardGenerator


async def main():
    parser = argparse.ArgumentParser(
        description="Generate e-ink dashboards via LLM and send to eink_mcp"
    )
    parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="Prompt describing the dashboard to generate",
    )
    parser.add_argument(
        "--context", "-c",
        type=Path,
        help="JSON file with context data to inject",
    )
    parser.add_argument(
        "--template", "-t",
        help="Template name to use (from templates/ dir)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output image path (default: auto-generated in output/)",
    )
    parser.add_argument(
        "--send", "-s",
        action="store_true",
        help="Send to eink_mcp content plan after rendering",
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=60,
        help="Display duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--priority",
        type=int,
        default=0,
        help="Content priority (higher = shown sooner)",
    )
    parser.add_argument(
        "--html-only",
        action="store_true",
        help="Only output HTML, don't render",
    )
    parser.add_argument(
        "--save-html",
        type=Path,
        help="Save generated HTML to file",
    )

    args = parser.parse_args()

    # Load context if provided
    context = None
    if args.context:
        if args.context.exists():
            context = json.loads(args.context.read_text())
        else:
            print(f"Error: Context file not found: {args.context}", file=sys.stderr)
            sys.exit(1)

    gen = DashboardGenerator()

    # Generate HTML
    print(f"Generating dashboard with {args.template or 'default'} template...")
    html = await gen.generate_html(args.prompt, context, args.template)

    if args.save_html:
        args.save_html.write_text(html)
        print(f"HTML saved to: {args.save_html}")

    if args.html_only:
        print(html)
        return

    # Render to image
    print("Rendering to image...")
    image_path = await gen.render(html, args.output)
    print(f"Image saved to: {image_path}")

    # Send to eink_mcp if requested
    if args.send:
        print(f"Sending to eink_mcp (duration: {args.duration}s)...")
        result = await gen.send_to_plan(
            image_path,
            duration=args.duration,
            priority=args.priority,
        )
        print(f"Sent successfully: {result}")


if __name__ == "__main__":
    asyncio.run(main())

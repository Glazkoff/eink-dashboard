#!/usr/bin/env python3
"""CLI for E-Ink Dashboard Generator with VLM Critic."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from generator import DashboardGenerator
from critic import DashboardCritic, CriticVerdict


async def main():
    parser = argparse.ArgumentParser(
        description="Generate e-ink dashboards via LLM with VLM quality check"
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

    # Critic options
    parser.add_argument(
        "--critic",
        action="store_true",
        help="Enable VLM critic to validate generated image",
    )
    parser.add_argument(
        "--critic-model",
        default="openai/gpt-4o-mini",
        help="VLM model for critic (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retry attempts if critic rejects (default: 3)",
    )
    parser.add_argument(
        "--skip-critic",
        action="store_true",
        help="Skip critic even if enabled (useful for testing)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Minimum score to approve (default: 0.7)",
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
    critic = None

    if args.critic and not args.skip_critic:
        critic = DashboardCritic(
            model=args.critic_model,
            threshold_approve=args.threshold,
        )
        print(f"Critic enabled (model: {args.critic_model}, threshold: {args.threshold})")

    # Generation loop with critic feedback
    current_prompt = args.prompt
    attempt = 0
    best_result = None
    best_score = 0

    while attempt <= args.max_retries:
        attempt += 1
        print(f"\n=== Attempt {attempt}/{args.max_retries + 1} ===")

        # Generate HTML
        print(f"Generating dashboard...")
        html = await gen.generate_html(current_prompt, context, args.template)

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

        # Critic evaluation
        if critic:
            print("\nCritic evaluating...")
            result = await critic.evaluate(
                image_path,
                prompt=args.prompt,
                template=args.template,
            )

            print(f"Score: {result.score:.2f}")
            print(f"Verdict: {result.verdict.value}")

            if result.issues:
                print("Issues found:")
                for issue in result.issues:
                    print(f"  - {issue}")

            if result.suggestions:
                print("Suggestions:")
                for suggestion in result.suggestions:
                    print(f"  - {suggestion}")

            # Track best attempt
            if result.score > best_score:
                best_score = result.score
                best_result = (image_path, result)

            # Check verdict
            if result.verdict == CriticVerdict.APPROVE:
                print("\n✓ Approved by critic!")
                break

            if result.verdict == CriticVerdict.ABORT:
                print("\n✗ Aborted by critic - fundamental issues")
                if best_result and best_score >= 0.5:
                    print(f"Using best attempt (score: {best_score:.2f})")
                    image_path = best_result[0]
                    break
                sys.exit(1)

            # Retry with feedback
            if attempt <= args.max_retries:
                feedback = critic.get_feedback_prompt(result)
                current_prompt = f"{args.prompt}\n\n{feedback}"
                print(f"\nRetrying with critic feedback...")
        else:
            # No critic, just proceed
            break

    # Send to eink_mcp if requested
    if args.send:
        print(f"\nSending to eink_mcp (duration: {args.duration}s)...")
        result = await gen.send_to_plan(
            image_path,
            duration=args.duration,
            priority=args.priority,
        )
        print(f"Sent successfully: {result}")
    else:
        print(f"\nImage ready: {image_path}")
        if args.critic and best_result:
            print(f"Final score: {best_score:.2f}")


if __name__ == "__main__":
    asyncio.run(main())

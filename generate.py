#!/usr/bin/env python3
"""CLI for E-Ink Dashboard Generator with VLM Critic and Template Learning."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from generator import DashboardGenerator
from critic import DashboardCritic, CriticVerdict
from template_registry import TemplateRegistry


async def main():
    parser = argparse.ArgumentParser(
        description="Generate e-ink dashboards via LLM with VLM quality check and template learning"
    )

    # Basic options
    parser.add_argument(
        "--prompt", "-p",
        help="Prompt describing the dashboard to generate",
    )
    parser.add_argument(
        "--context", "-c",
        type=Path,
        help="JSON file with context data to inject",
    )
    parser.add_argument(
        "--template", "-t",
        help="Built-in template name to use (from templates/ dir)",
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

    # Template learning options
    parser.add_argument(
        "--learn",
        action="store_true",
        help="Enable template learning - reuse successful templates for similar prompts",
    )
    parser.add_argument(
        "--no-learn",
        action="store_true",
        help="Disable template learning (even if enabled by default)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.7,
        help="Minimum confidence to reuse template (default: 0.7)",
    )
    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="List learned templates and exit",
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

    # Output options
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

    # Handle --list-templates
    if args.list_templates:
        registry = TemplateRegistry()
        stats = registry.get_stats()
        templates = registry.list_templates()
        
        if not templates:
            print("No learned templates yet.")
            return

        print(f"Learned templates ({stats['total_templates']}):")
        print(f"  Total uses: {stats['total_uses']}")
        print(f"  Avg success rate: {stats['avg_success_rate']:.0%}\n")
        
        for t in templates:
            print(f"  {t.id}: {t.name}")
            print(f"    Description: {t.description}")
            print(f"    Uses: {t.uses} | Success rate: {t.success_rate:.0%} | Avg score: {t.avg_score:.2f}")
            print(f"    Tags: {', '.join(t.tags)}")
            if t.example_prompts:
                print(f"    Example: \"{t.example_prompts[0][:60]}...\"")
            print()
        return

    # Require prompt for generation
    if not args.prompt:
        parser.error("--prompt is required for generation (or use --list-templates)")

    # Load context if provided
    context = None
    if args.context:
        if args.context.exists():
            context = json.loads(args.context.read_text())
        else:
            print(f"Error: Context file not found: {args.context}", file=sys.stderr)
            sys.exit(1)

    # Determine template learning
    use_learning = args.learn and not args.no_learn and not args.template

    # Initialize generator
    gen = DashboardGenerator(use_template_learning=use_learning)
    critic = None

    if args.critic and not args.skip_critic:
        critic = DashboardCritic(
            model=args.critic_model,
            threshold_approve=args.threshold,
        )
        print(f"Critic enabled (model: {args.critic_model}, threshold: {args.threshold})")

    if use_learning:
        print("Template learning enabled")

    # Generation loop with critic feedback
    current_prompt = args.prompt
    attempt = 0
    best_result = None
    best_score = 0
    best_template_id = "default"
    is_new_template = False

    while attempt <= args.max_retries:
        attempt += 1
        print(f"\n=== Attempt {attempt}/{args.max_retries + 1} ===")

        # Generate HTML
        print(f"Generating dashboard...")

        if use_learning:
            html, template_id, is_new = await gen.generate_with_template_learning(
                current_prompt,
                context,
                min_confidence=args.min_confidence,
            )
            if is_new:
                print(f"Created new template: {template_id}")
            else:
                print(f"Using learned template: {template_id}")
            best_template_id = template_id
            is_new_template = is_new
        else:
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
                template=best_template_id,
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

            # Record template result for learning
            if use_learning:
                success = result.verdict == CriticVerdict.APPROVE
                gen.record_template_result(
                    best_template_id,
                    success=success,
                    score=result.score,
                    prompt=args.prompt,
                )
                if success:
                    print(f"Template {best_template_id} marked as successful")

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
            # No critic, mark as success for template learning
            if use_learning:
                gen.record_template_result(
                    best_template_id,
                    success=True,
                    score=1.0,
                    prompt=args.prompt,
                )
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
        if use_learning:
            status = "new" if is_new_template else "reused"
            print(f"Template: {best_template_id} ({status})")


if __name__ == "__main__":
    asyncio.run(main())

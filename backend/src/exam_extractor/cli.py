"""Command-line entry point for the Phase 1 deterministic pipeline."""

import argparse
from pathlib import Path

from .config import PipelineConfig
from .errors import ExtractorError
from .pipeline import run_pipeline
from .services.profiles import apply_profile


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser."""
    parser = argparse.ArgumentParser(
        prog="exam-extractor",
        description="Extract captions, speech-ready audio, visual frames, OCR, and Markdown from media.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="process one YouTube URL or local media file")
    run.add_argument("source", help="YouTube URL or local video/audio path")
    run.add_argument("--config", type=Path, help="TOML configuration file")
    run.add_argument("--output", type=Path, help="job output root; overrides config output_dir")
    run.add_argument("--profile", help="profile label stored in the job manifest")
    run.add_argument("--transcript", action="store_true", help="also write transcript.md")
    run.add_argument("--force", action="store_true", help="discard this generated job and rerun")
    run.add_argument("--verbose", action="store_true", help="print detailed errors")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = build_parser().parse_args(argv)
    if args.command != "run":
        return 2
    try:
        config = PipelineConfig.from_toml(args.config) if args.config else PipelineConfig()
        if args.profile:
            apply_profile(config, args.profile)
        if args.transcript:
            config.output.transcript = True
        workspace = run_pipeline(
            args.source,
            config,
            output_root=args.output,
            force=args.force,
        )
        print(f"Output: {workspace}")
        return 0
    except ExtractorError as error:
        print(f"ERROR [{error.code.value}] {error.message}")
        if error.stage:
            print(f"Stage: {error.stage}")
        if error.suggestion:
            print(f"Suggestion: {error.suggestion}")
        if args.verbose and error.details:
            print(f"Details: {error.details}")
        return 1
    except (OSError, ValueError) as error:
        print(f"ERROR [configuration] {error}")
        return 1

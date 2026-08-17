"""Command-line interface for the fail-closed generator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .errors import GeneratorError
from .seeds import derive_seed
from .settings import load_settings
from .transaction import build_array_stage


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="simple-synthetic-eeg")
    subcommands = root.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate-settings", help="validate the frozen settings JSON")
    validate.add_argument("--settings", type=Path, required=True)

    seed = subcommands.add_parser("derive-seed", help="print one deterministic seed record")
    seed.add_argument("--subject", required=True)
    seed.add_argument("--stream", required=True)

    generate = subcommands.add_parser("generate", help="build and validate one new array stage")
    generate.add_argument("--settings", type=Path, required=True)
    generate.add_argument("--source-root", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    return root


def run(arguments: Sequence[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    if args.command == "validate-settings":
        settings = load_settings(args.settings)
        print(f"valid {settings.values['schema']}")
        return 0
    if args.command == "derive-seed":
        seed = derive_seed(args.subject, args.stream)
        print(
            json.dumps(
                {
                    "stream": seed.stream,
                    "seed32": seed.seed32,
                    "seed128": seed.seed128,
                    "sha256": seed.sha256,
                    "subject_id": seed.subject_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    if args.command == "generate":
        settings = load_settings(args.settings)
        output = build_array_stage(
            output=args.output,
            settings=settings,
            source_root=args.source_root,
        )
        print(output)
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


def main() -> None:
    try:
        raise SystemExit(run())
    except GeneratorError as exc:
        raise SystemExit(f"error: {exc}") from exc


if __name__ == "__main__":
    main()

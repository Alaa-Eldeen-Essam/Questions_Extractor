"""External executable discovery and safe subprocess execution."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from ..errors import ErrorCode, ExtractorError


def executable(name: str, environment_name: str) -> str:
    """Resolve an executable from an environment override or ``PATH``."""
    configured = os.environ.get(environment_name)
    candidate = configured or shutil.which(name)
    if not candidate:
        raise ExtractorError(
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            message=f"Required executable was not found: {name}.",
            provider=name,
            suggestion=(
                f"Install {name} and add it to PATH, or set {environment_name} "
                f"to its absolute executable path."
            ),
        )
    return candidate


def run_checked(
    args: Sequence[str],
    *,
    stage: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command and turn failures into an actionable extractor error."""
    try:
        result = subprocess.run(
            list(args),
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ExtractorError(
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            message=f"Could not start command {args[0]!r}: {exc}",
            stage=stage,
            provider=args[0],
            suggestion="Check that the executable is installed and accessible.",
        ) from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-2000:]
        raise ExtractorError(
            code=ErrorCode.MEDIA_UNREADABLE,
            message=f"Command failed during {stage}: {args[0]}.",
            stage=stage,
            provider=args[0],
            suggestion="Review the command output and verify the input media is readable.",
            details={"returncode": result.returncode, "output": detail},
        )
    return result

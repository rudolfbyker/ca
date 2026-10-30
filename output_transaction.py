"""
Stage certificate outputs before replacing working files.
"""

from contextlib import contextmanager
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory
from typing import Iterator, Tuple


@contextmanager
def output_transaction(*, out_dir: Path, filenames: Tuple[str, ...]) -> Iterator[Path]:
    """
    Preserve working files until generation and validation succeed.

    Args:
        out_dir: Directory containing the working files.
        filenames: Output filenames to stage and publish together.

    Yields:
        Directory in which to generate and validate the outputs.

    Raises:
        BaseException: Propagates failures after restoring any published files.
    """
    with TemporaryDirectory(prefix=".certificate-", dir=out_dir.parent) as temporary:
        staging = Path(temporary)
        backup = staging / "backup"
        backup.mkdir()
        for filename in filenames:
            source = out_dir / filename
            if source.exists():
                copy2(source, staging / filename)
                copy2(source, backup / filename)
        yield staging
        published = []
        try:
            for filename in filenames:
                source = staging / filename
                if source.exists():
                    published.append(filename)
                    source.replace(out_dir / filename)
        except BaseException:
            for filename in reversed(published):
                original = backup / filename
                destination = out_dir / filename
                if original.exists():
                    original.replace(destination)
                else:
                    destination.unlink(missing_ok=True)
            raise

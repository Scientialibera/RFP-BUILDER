"""
Run directory helpers shared across workflow and step endpoints.
"""

from datetime import datetime
from pathlib import Path


RUN_SUBDIRECTORIES = [
    "word_document",
    "image_assets",
    "diagrams",
    "llm_interactions",
    "execution_logs",
    "metadata",
    "code_snapshots",
    "documents",
    "revisions",
]


def create_unique_run_directory(output_root: Path) -> Path:
    """Create a unique run directory with the standard subdirectory layout."""
    output_root.mkdir(parents=True, exist_ok=True)

    run_name = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_dir = output_root / run_name
    suffix = 1
    while run_dir.exists():
        run_dir = output_root / f"{run_name}_{suffix:02d}"
        suffix += 1

    for subdir_name in RUN_SUBDIRECTORIES:
        (run_dir / subdir_name).mkdir(parents=True, exist_ok=True)

    return run_dir

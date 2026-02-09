"""
Azure Blob storage helpers for run artifact uploads.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from app.core.config import get_config


logger = logging.getLogger(__name__)


class RunBlobStorage:
    """Uploads run directories to Azure Blob storage."""

    def __init__(self) -> None:
        self._config = get_config().storage
        self._client: Optional[BlobServiceClient] = None
        self._container_ensured = False

    @property
    def enabled(self) -> bool:
        return bool(self._config.use_blob_storage and self._config.blob_account_name.strip())

    def _get_client(self) -> BlobServiceClient:
        if self._client is None:
            account_name = self._config.blob_account_name.strip()
            account_url = f"https://{account_name}.blob.core.windows.net"
            self._client = BlobServiceClient(
                account_url=account_url,
                credential=DefaultAzureCredential(),
            )
        return self._client

    def _ensure_container(self) -> None:
        if self._container_ensured:
            return
        client = self._get_client()
        container_name = self._config.blob_container_name.strip() or "rfps"
        container_client = client.get_container_client(container_name)
        container_client.create_container()
        self._container_ensured = True

    def sync_run_directory(self, run_dir: Path) -> None:
        """Upload all files under run_dir to blob path: <runs_prefix>/<run_id>/..."""
        if not self.enabled:
            return
        if not run_dir.exists():
            return

        try:
            self._ensure_container()
        except Exception:
            # Container may already exist; continue.
            self._container_ensured = True

        client = self._get_client()
        container_name = self._config.blob_container_name.strip() or "rfps"
        runs_prefix = (self._config.blob_runs_prefix or "runs").strip().strip("/")
        run_id = run_dir.name

        container_client = client.get_container_client(container_name)
        uploaded = 0
        for file_path in run_dir.rglob("*"):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(run_dir).as_posix()
            blob_name = f"{runs_prefix}/{run_id}/{relative}" if runs_prefix else f"{run_id}/{relative}"
            with open(file_path, "rb") as stream:
                container_client.upload_blob(name=blob_name, data=stream, overwrite=True)
            uploaded += 1
        logger.info("Blob sync complete for %s (%d files)", run_id, uploaded)


_blob_storage: Optional[RunBlobStorage] = None


def get_blob_storage() -> RunBlobStorage:
    global _blob_storage
    if _blob_storage is None:
        _blob_storage = RunBlobStorage()
    return _blob_storage


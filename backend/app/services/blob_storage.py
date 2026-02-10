"""
Azure Blob storage helpers for run artifact uploads.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from azure.core.exceptions import ResourceExistsError
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
        try:
            container_client.create_container()
        except ResourceExistsError:
            pass
        self._container_ensured = True

    def _container_client(self):
        self._ensure_container()
        client = self._get_client()
        container_name = self._config.blob_container_name.strip() or "rfps"
        return client.get_container_client(container_name)

    def _run_prefix(self, run_id: str) -> str:
        runs_prefix = (self._config.blob_runs_prefix or "runs").strip().strip("/")
        return f"{runs_prefix}/{run_id}/" if runs_prefix else f"{run_id}/"

    def sync_run_directory(self, run_dir: Path) -> None:
        """Upload all files under run_dir to blob path: <runs_prefix>/<run_id>/..."""
        if not self.enabled:
            return
        if not run_dir.exists():
            return

        container_client = self._container_client()

        run_id = run_dir.name

        uploaded = 0
        run_prefix = self._run_prefix(run_id)
        for file_path in run_dir.rglob("*"):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(run_dir).as_posix()
            blob_name = f"{run_prefix}{relative}"
            with open(file_path, "rb") as stream:
                container_client.upload_blob(name=blob_name, data=stream, overwrite=True)
            uploaded += 1
        logger.info("Blob sync complete for %s (%d files)", run_id, uploaded)

    def list_run_ids(self) -> list[str]:
        if not self.enabled:
            return []
        container_client = self._container_client()
        runs_prefix = (self._config.blob_runs_prefix or "runs").strip().strip("/")
        prefix = f"{runs_prefix}/" if runs_prefix else ""
        run_ids: set[str] = set()
        for blob in container_client.list_blobs(name_starts_with=prefix):
            name = blob.name
            if prefix and not name.startswith(prefix):
                continue
            remainder = name[len(prefix):] if prefix else name
            parts = remainder.split("/", 1)
            if parts and parts[0].startswith("run_"):
                run_ids.add(parts[0])
        return sorted(run_ids)

    def list_run_blob_names(self, run_id: str) -> list[str]:
        if not self.enabled:
            return []
        container_client = self._container_client()
        prefix = self._run_prefix(run_id)
        return [blob.name for blob in container_client.list_blobs(name_starts_with=prefix)]

    def blob_exists(self, run_id: str, relative_path: str) -> bool:
        if not self.enabled:
            return False
        container_client = self._container_client()
        blob_name = f"{self._run_prefix(run_id)}{relative_path.strip('/')}"
        blob_client = container_client.get_blob_client(blob_name)
        return blob_client.exists()

    def download_blob_bytes(self, run_id: str, relative_path: str) -> Optional[bytes]:
        if not self.enabled:
            return None
        container_client = self._container_client()
        blob_name = f"{self._run_prefix(run_id)}{relative_path.strip('/')}"
        blob_client = container_client.get_blob_client(blob_name)
        if not blob_client.exists():
            return None
        stream = blob_client.download_blob()
        return stream.readall()

    def hydrate_run_directory(self, run_id: str, target_dir: Path) -> bool:
        """Download all blobs for a run into target_dir. Returns True if any blobs were found."""
        if not self.enabled:
            return False
        blob_names = self.list_run_blob_names(run_id)
        if not blob_names:
            return False

        target_dir.mkdir(parents=True, exist_ok=True)
        prefix = self._run_prefix(run_id)
        container_client = self._container_client()
        for blob_name in blob_names:
            if not blob_name.startswith(prefix):
                continue
            relative = blob_name[len(prefix):]
            if not relative:
                continue
            file_path = target_dir / relative
            file_path.parent.mkdir(parents=True, exist_ok=True)
            blob_client = container_client.get_blob_client(blob_name)
            data = blob_client.download_blob().readall()
            with open(file_path, "wb") as f:
                f.write(data)
        return True


_blob_storage: Optional[RunBlobStorage] = None


def get_blob_storage() -> RunBlobStorage:
    global _blob_storage
    if _blob_storage is None:
        _blob_storage = RunBlobStorage()
    return _blob_storage

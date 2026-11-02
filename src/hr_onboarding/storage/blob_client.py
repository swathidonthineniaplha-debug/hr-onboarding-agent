"""Thin wrapper around Azure Blob Storage, plus an in-memory version for tests.

AzureBlobStore is built from a connection string only, so the same code talks
to Azurite locally ("UseDevelopmentStorage=true") and to Azure in the cloud.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient


class BlobStore(ABC):
    @abstractmethod
    def ensure_containers(self, names: Iterable[str]) -> None: ...

    @abstractmethod
    def upload(self, container: str, name: str, data: bytes) -> None:
        """Create or overwrite a blob."""

    @abstractmethod
    def download(self, container: str, name: str) -> bytes: ...

    @abstractmethod
    def delete(self, container: str, name: str) -> None: ...

    @abstractmethod
    def list_names(self, container: str) -> list[str]: ...

    @abstractmethod
    def set_metadata(self, container: str, name: str, metadata: dict[str, str]) -> None: ...

    @abstractmethod
    def url(self, container: str, name: str) -> str: ...


class AzureBlobStore(BlobStore):
    def __init__(self, connection_string: str) -> None:
        self._service = BlobServiceClient.from_connection_string(connection_string)

    def ensure_containers(self, names: Iterable[str]) -> None:
        for name in names:
            try:
                self._service.create_container(name)
            except ResourceExistsError:
                pass

    def upload(self, container: str, name: str, data: bytes) -> None:
        self._service.get_blob_client(container, name).upload_blob(data, overwrite=True)

    def download(self, container: str, name: str) -> bytes:
        return self._service.get_blob_client(container, name).download_blob().readall()

    def delete(self, container: str, name: str) -> None:
        self._service.get_blob_client(container, name).delete_blob()

    def list_names(self, container: str) -> list[str]:
        return [blob.name for blob in self._service.get_container_client(container).list_blobs()]

    def set_metadata(self, container: str, name: str, metadata: dict[str, str]) -> None:
        self._service.get_blob_client(container, name).set_blob_metadata(metadata)

    def url(self, container: str, name: str) -> str:
        return self._service.get_blob_client(container, name).url


class InMemoryBlobStore(BlobStore):
    """Dictionary-backed store with the same behaviour, for tests and offline runs."""

    def __init__(self) -> None:
        self.blobs: dict[str, dict[str, bytes]] = {}
        self.metadata: dict[tuple[str, str], dict[str, str]] = {}

    def ensure_containers(self, names: Iterable[str]) -> None:
        for name in names:
            self.blobs.setdefault(name, {})

    def upload(self, container: str, name: str, data: bytes) -> None:
        self.blobs[container][name] = data
        self.metadata.pop((container, name), None)  # overwriting clears metadata, as in Azure

    def download(self, container: str, name: str) -> bytes:
        return self.blobs[container][name]

    def delete(self, container: str, name: str) -> None:
        del self.blobs[container][name]
        self.metadata.pop((container, name), None)

    def list_names(self, container: str) -> list[str]:
        return sorted(self.blobs[container])

    def set_metadata(self, container: str, name: str, metadata: dict[str, str]) -> None:
        if name not in self.blobs[container]:
            raise KeyError(f"{container}/{name}")
        self.metadata[(container, name)] = dict(metadata)

    def url(self, container: str, name: str) -> str:
        return f"memory://{container}/{name}"

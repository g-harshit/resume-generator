"""Where uploaded files live: local disk in development, Cloudflare R2 when deployed
(chosen by whether an R2 bucket is configured)."""

import secrets
from functools import cache
from pathlib import Path
from typing import Protocol

from app.config import get_settings


class Storage(Protocol):
    def put(self, data: bytes, *, suffix: str) -> str:
        """Store `data` and return the key to read it back with."""

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):  # keys are ours, but never trust a path
            raise ValueError(f"Bad storage key: {key}")
        return path

    def put(self, data: bytes, *, suffix: str) -> str:
        # Random names: the user's filename never touches the filesystem.
        key = f"{secrets.token_hex(16)}{suffix}"
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class R2Storage:
    """Cloudflare R2 through its S3 API. Objects are private: the API reads them back
    for the person who uploaded them; nothing is ever served from the bucket."""

    def __init__(self, bucket: str, client):
        self.bucket = bucket
        self.client = client

    @classmethod
    def from_settings(cls) -> "R2Storage":
        import boto3  # only needed when deployed
        from botocore.config import Config

        s = get_settings()
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{s.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=s.r2_access_key_id,
            aws_secret_access_key=s.r2_secret_access_key,
            region_name="auto",
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
        )
        return cls(s.r2_bucket, client)

    def put(self, data: bytes, *, suffix: str) -> str:
        key = f"uploads/{secrets.token_hex(16)}{suffix}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


@cache
def _r2() -> R2Storage:
    return R2Storage.from_settings()


def get_storage() -> Storage:
    if get_settings().r2_bucket:
        return _r2()
    return LocalStorage(get_settings().upload_dir)

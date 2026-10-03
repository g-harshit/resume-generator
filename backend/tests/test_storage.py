"""Where uploads live: local disk, or R2 when a bucket is configured."""

import io

import pytest

from app.services import storage
from app.services.storage import LocalStorage, R2Storage


class FakeS3:
    """The three S3 calls R2Storage makes, in memory."""

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket, Key, Body):
        self.objects[(Bucket, Key)] = Body

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


def test_r2_stores_reads_and_deletes_by_random_key():
    s3 = FakeS3()
    r2 = R2Storage("resumes", s3)
    key = r2.put(b"%PDF-1.7 hello", suffix=".pdf")
    assert key.startswith("uploads/") and key.endswith(".pdf") and len(key) > 30
    assert r2.get(key) == b"%PDF-1.7 hello"
    assert r2.put(b"x", suffix=".pdf") != key  # never reused
    r2.delete(key)
    assert ("resumes", key) not in s3.objects


def test_local_disk_is_used_without_a_bucket(monkeypatch, tmp_path):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "r2_bucket", "")
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    assert isinstance(storage.get_storage(), LocalStorage)


def test_r2_is_used_when_a_bucket_is_set(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "r2_bucket", "resumes")
    monkeypatch.setattr(storage, "_r2", lambda: R2Storage("resumes", FakeS3()))
    assert isinstance(storage.get_storage(), R2Storage)


def test_a_local_key_cant_escape_the_folder(tmp_path):
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).get("../secrets.txt")

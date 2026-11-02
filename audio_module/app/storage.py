"""
Object Storage абстракция.

Поддерживаемые провайдеры:
  - local_dev: файлы на диске (./storage)
  - s3: Amazon S3
  - minio: MinIO (S3-совместимый)

Путь к файлу формируется по шаблону из схемы:
  /interviews/{interview_id}/{artifact_type}/{filename}

Сохраняется обратная совместимость с save_to_json().
"""
import hashlib, json, logging, os, shutil
from typing import Optional, Tuple
from app.config import settings

logger = logging.getLogger("storage")
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)


def save_to_json(result_data: dict):
    """Обратная совместимость: сохранение результата в JSON."""
    file_path = os.path.join(RESULTS_DIR, f"{result_data.get('_id', 'unknown')}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=4)


def _build_storage_key(interview_id: str, artifact_type: str, filename: str) -> str:
    """Построить ключ хранения по схеме из диаграммы."""
    type_folder_map = {
        "resume": "resume",
        "cover_letter": "cover_letter",
        "test_task_result": "test_task",
        "audio_recording": "audio",
        "transcript_text": "transcript",
        "video_frames": "frames",
        "auditor_comment": "auditor",
        "other": "other",
    }
    folder = type_folder_map.get(artifact_type, artifact_type)
    return f"interviews/{interview_id}/{folder}/{filename}"


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ═══════════════════════════════════════════════════════════
#  Local Dev Storage
# ═══════════════════════════════════════════════════════════

def _local_save(storage_key: str, data: bytes) -> str:
    full_path = os.path.join(settings.STORAGE_BASE_PATH, storage_key)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(data)
    return full_path


def _local_read(storage_key: str) -> Optional[bytes]:
    full_path = os.path.join(settings.STORAGE_BASE_PATH, storage_key)
    if not os.path.exists(full_path):
        return None
    with open(full_path, "rb") as f:
        return f.read()


def _local_delete(storage_key: str) -> bool:
    full_path = os.path.join(settings.STORAGE_BASE_PATH, storage_key)
    if os.path.exists(full_path):
        os.remove(full_path)
        return True
    return False


# ═══════════════════════════════════════════════════════════
#  S3 / MinIO Storage (заготовка)
# ═══════════════════════════════════════════════════════════

def _s3_save(storage_key: str, data: bytes, content_type: str = None) -> str:
    """Сохранить файл в S3/MinIO. Требуются S3_* переменные в .env."""
    try:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        extra = {"ContentType": content_type} if content_type else {}
        client.put_object(Bucket=settings.S3_BUCKET_NAME, Key=storage_key, Body=data, **extra)
        return f"s3://{settings.S3_BUCKET_NAME}/{storage_key}"
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        # Fallback на local
        return _local_save(storage_key, data)


def _s3_read(storage_key: str) -> Optional[bytes]:
    try:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        response = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=storage_key)
        return response["Body"].read()
    except Exception as e:
        logger.error(f"S3 read failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════
#  Публичный API
# ═══════════════════════════════════════════════════════════

def save_file(
    interview_id: str,
    artifact_type: str,
    data: bytes,
    original_name: str,
    content_type: str = None,
) -> Tuple[str, str, int]:
    """
    Сохранить файл в Object Storage.
    Returns: (storage_key, checksum_sha256, size_bytes)
    """
    storage_key = _build_storage_key(interview_id, artifact_type, original_name)
    checksum = _compute_sha256(data)
    size = len(data)

    provider = settings.STORAGE_PROVIDER
    if provider in ("s3", "minio"):
        _s3_save(storage_key, data, content_type)
    else:
        _local_save(storage_key, data)

    logger.info(f"Файл сохранён [{provider}]: {storage_key} ({size} bytes)")
    return storage_key, checksum, size


def read_file(storage_key: str) -> Optional[bytes]:
    """Прочитать файл из Object Storage."""
    provider = settings.STORAGE_PROVIDER
    if provider in ("s3", "minio"):
        return _s3_read(storage_key)
    return _local_read(storage_key)


def delete_file(storage_key: str) -> bool:
    """Удалить файл из Object Storage."""
    provider = settings.STORAGE_PROVIDER
    if provider in ("s3", "minio"):
        logger.warning("S3 delete не реализован — используйте консоль AWS")
        return False
    return _local_delete(storage_key)

"""
utils/azure_storage.py — Azure Blob Storage integration for SRGEC-SIMS
Handles upload and SAS URL generation for invoice scans, complaint photos,
quotations, POs and other documents.
"""
import os
from datetime import datetime, timedelta, timezone

AZURE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_CONTAINER_NAME    = os.environ.get("AZURE_CONTAINER_NAME", "sims-uploads")


def _get_client():
    """Get BlobServiceClient."""
    from azure.storage.blob import BlobServiceClient
    return BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)


def upload_file(file_bytes: bytes, blob_name: str, content_type: str = "application/octet-stream") -> str:
    """
    Upload file bytes to Azure Blob Storage.
    Returns the blob name (stored in DB).
    """
    try:
        client = _get_client()
        container = client.get_container_client(AZURE_CONTAINER_NAME)
        blob = container.get_blob_client(blob_name)
        blob.upload_blob(file_bytes, overwrite=True,
                        content_settings={"content_type": content_type})
        return blob_name
    except Exception as ex:
        raise Exception(f"Azure upload failed: {ex}")


def get_sas_url(blob_name: str, expiry_hours: int = 2) -> str:
    """
    Generate a temporary SAS URL for viewing a private blob.
    URL expires after expiry_hours (default 2 hours).
    """
    try:
        from azure.storage.blob import generate_blob_sas, BlobSasPermissions
        # Parse account name and key from connection string
        parts = dict(p.split("=", 1) for p in AZURE_CONNECTION_STRING.split(";") if "=" in p)
        account_name = parts.get("AccountName", "")
        account_key  = parts.get("AccountKey", "")
        
        expiry = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=AZURE_CONTAINER_NAME,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry
        )
        return f"https://{account_name}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{blob_name}?{sas_token}"
    except Exception as ex:
        raise Exception(f"SAS URL generation failed: {ex}")


def delete_file(blob_name: str):
    """Delete a blob from Azure Storage."""
    try:
        client = _get_client()
        container = client.get_container_client(AZURE_CONTAINER_NAME)
        container.get_blob_client(blob_name).delete_blob()
    except Exception:
        pass  # Ignore delete errors


def is_azure_configured() -> bool:
    """Check if Azure storage is configured."""
    return bool(AZURE_CONNECTION_STRING)

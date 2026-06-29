"""
utils/azure_storage.py — Azure Blob Storage integration for SRGEC-SIMS
"""
import os
from datetime import datetime, timedelta, timezone

AZURE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_CONTAINER_NAME    = os.environ.get("AZURE_CONTAINER_NAME", "sims-uploads")


def _get_client():
    from azure.storage.blob import BlobServiceClient
    return BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)


def upload_file(file_bytes, blob_name, content_type="application/octet-stream"):
    try:
        client = _get_client()
        container = client.get_container_client(AZURE_CONTAINER_NAME)
        blob = container.get_blob_client(blob_name)
        from azure.storage.blob import ContentSettings
        blob.upload_blob(file_bytes, overwrite=True,
                        content_settings=ContentSettings(content_type=content_type))
        return blob_name
    except Exception as ex:
        raise Exception(f"Azure upload failed: {ex}")


def get_sas_url(blob_name, expiry_hours=2):
    try:
        from azure.storage.blob import generate_blob_sas, BlobSasPermissions
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


def delete_file(blob_name):
    try:
        client = _get_client()
        container = client.get_container_client(AZURE_CONTAINER_NAME)
        container.get_blob_client(blob_name).delete_blob()
    except Exception:
        pass


def is_azure_configured():
    return bool(AZURE_CONNECTION_STRING)

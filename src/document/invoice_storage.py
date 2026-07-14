import os

from supabase import Client, create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

BUCKET_NAME = "Invoices"

_client: Client | None = None


def get_storage_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set to use invoice storage."
            )
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _client


def storage_path_for(firm_id: str, invoice_id: str) -> str:
    """Canonical path used for every invoice PDF in the bucket."""
    return f"{firm_id}/{invoice_id}.pdf"


def upload_invoice_pdf(firm_id: str, invoice_id: str, local_file_path: str) -> str:
    """
    Uploads a locally-generated PDF (e.g. from /tmp) to Supabase Storage.
    Returns the storage path (not a public URL — bucket should be private
    since these are financial documents; we download via the service key
    when resending rather than exposing a public link).
    """
    client = get_storage_client()
    path = storage_path_for(firm_id, invoice_id)

    with open(local_file_path, "rb") as f:
        file_bytes = f.read()

    client.storage.from_(BUCKET_NAME).upload(
        path=path,
        file=file_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    return path


def download_invoice_pdf(storage_path: str, destination_local_path: str) -> str:
    """
    Downloads a previously-stored invoice PDF from Supabase Storage to a
    local path (use /tmp in Lambda). Returns the local path written.
    """
    client = get_storage_client()
    file_bytes = client.storage.from_(BUCKET_NAME).download(storage_path)

    with open(destination_local_path, "wb") as f:
        f.write(file_bytes)

    return destination_local_path

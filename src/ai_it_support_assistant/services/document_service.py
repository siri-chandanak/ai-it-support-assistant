from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

ALLOWED_EXTENSIONS = {".txt", ".md"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


class InvalidDocumentError(Exception):
    pass


class DocumentTooLargeError(Exception):
    pass


async def save_document(
    file: UploadFile,
    storage_path: str,
) -> tuple[str, Path, int]:
    filename = file.filename

    if not filename:
        raise InvalidDocumentError("Uploaded file must have a filename.")

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise InvalidDocumentError(f"Unsupported file type: {extension or 'unknown'}")

    contents = await file.read()

    size_bytes = len(contents)

    if size_bytes == 0:
        raise InvalidDocumentError("Uploaded file is empty.")

    if size_bytes > MAX_FILE_SIZE_BYTES:
        raise DocumentTooLargeError(f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES} bytes.")

    document_id = str(uuid4())

    destination_directory = Path(storage_path)
    destination_directory.mkdir(parents=True, exist_ok=True)

    destination_path = destination_directory / f"{document_id}{extension}"

    destination_path.write_bytes(contents)

    return document_id, destination_path, size_bytes

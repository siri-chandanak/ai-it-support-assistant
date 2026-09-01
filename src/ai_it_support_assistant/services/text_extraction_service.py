from pathlib import Path

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}


class TextExtractionError(Exception):
    pass


def extract_text(file_path: Path) -> str:
    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_TEXT_EXTENSIONS:
        raise TextExtractionError(f"Text extraction is not supported for: {extension or 'unknown'}")

    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise TextExtractionError(f"Unable to decode document as UTF-8: {file_path.name}") from exc
    except OSError as exc:
        raise TextExtractionError(f"Unable to read document: {file_path.name}") from exc

    text = text.strip()

    if not text:
        raise TextExtractionError("Document contains no usable text.")

    return text

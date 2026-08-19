"""File-processing service configuration."""

from pathlib import Path

from src.shared.config import FileProcServiceSettings


settings = FileProcServiceSettings()

for directory in (settings.storage_dir, settings.upload_dir, settings.temp_dir):
    Path(directory).mkdir(parents=True, exist_ok=True)

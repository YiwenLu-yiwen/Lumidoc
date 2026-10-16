"""Probe the native Ollama endpoint from Docker, without exposing configuration."""
import json
import os
import sys
from urllib.request import urlopen

url = os.environ.get('NATIVE_OLLAMA_URL') or 'http://host.docker.internal:11434'
try:
    with urlopen(url.rstrip('/') + '/api/ps', timeout=3) as response:
        models = json.load(response).get('models', [])
    # Apple Silicon supports Metal even when no model is currently loaded.
    available = os.environ.get('APPLE_SILICON') == '1' or any(
        model.get('size_vram', 0) > 0 for model in models
    )
except Exception:
    available = False
sys.exit(0 if available else 1)

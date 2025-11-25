import io
import importlib

import pytest
from flask import Flask


@pytest.fixture
def app():
    """
    Provide the Flask app instance from backend.api_server.
    Import inside the fixture so tests don't run model loading
    at module import time in this file.
    """
    module = importlib.import_module("backend.api_server")
    assert isinstance(module.app, Flask)
    return module.app


@pytest.fixture
def client(app):
    """Flask test client fixture."""
    return app.test_client()


def test_transcribe_missing_file(client):
    """Should return 400 if no file is provided."""
    resp = client.post("/transcribe", data={})
    assert resp.status_code == 400
    json_data = resp.get_json()
    assert json_data["error"] == "No file provided"


def test_transcribe_unsupported_format(client):
    """Should return 400 for unsupported file extensions."""
    fake_file = (io.BytesIO(b"fake data"), "audio.txt")
    resp = client.post("/transcribe", data={"file": fake_file})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Unsupported file format"


def test_transcribe_success_mocked(client, monkeypatch):
    """
    End-to-end style test with a mocked transcription and keyword detection,
    so we don't need the real model or ffmpeg.
    """
    module = importlib.import_module("backend.api_server")

    def fake_transcribe_audio(path: str) -> str:
        return "Der Ball ist rot und blau."

    def fake_detect_keywords(text: str):
        return ["rot", "blau"]

    monkeypatch.setattr(module, "transcribe_audio", fake_transcribe_audio)
    monkeypatch.setattr(module, "detect_keywords", fake_detect_keywords)

    # Minimal valid WAV header bytes to satisfy pydub/ffmpeg in tests
    # (we mock transcribe, so content itself is not important)
    fake_audio_bytes = b"RIFF....WAVEfmt "  # very minimal stub

    fake_file = (io.BytesIO(fake_audio_bytes), "audio.wav")
    resp = client.post("/transcribe", data={"file": fake_file})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["text"] == "Der Ball ist rot und blau."
    assert data["keywords"] == ["rot", "blau"]
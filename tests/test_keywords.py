import importlib

def test_detect_keywords_basic(monkeypatch):
    """
    Ensure detect_keywords finds keywords case-insensitively
    and returns them with original casing.
    """
    api_server = importlib.import_module("backend.api_server")

    # Override keyword_set to control test data
    monkeypatch.setattr(api_server, "keyword_set", {"rot", "blau", "england"})

    text = "Der Ball ist rot und blau. England spielt heute."
    detected = api_server.detect_keywords(text)

    assert "rot" in detected
    assert "blau" in detected
    assert "England" in detected
    assert len(detected) == 3


def test_detect_keywords_punctuation(monkeypatch):
    """Keywords should be detected even with trailing punctuation."""
    api_server = importlib.import_module("backend.api_server")
    monkeypatch.setattr(api_server, "keyword_set", {"rot"})

    text = "Das Auto ist rot, wirklich rot!"
    detected = api_server.detect_keywords(text)

    assert detected.count("rot") == 2
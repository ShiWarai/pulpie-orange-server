from app.config import load_config


def test_load_config_defaults(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    cfg = load_config()
    assert cfg.server.port == 5000
    assert cfg.model.path.name == "model"
    assert cfg.extraction.max_input_bytes == 5_000_000
    assert cfg.api.key == ""


def test_api_key_from_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret-key")
    assert load_config().api.key == "secret-key"

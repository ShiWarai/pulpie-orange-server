from app.config import load_config


def test_load_config_defaults():
    cfg = load_config()
    assert cfg.server.port == 5000
    assert cfg.model.path.name == "model"
    assert cfg.extraction.max_input_bytes == 5_000_000

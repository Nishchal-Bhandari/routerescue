import pytest


@pytest.fixture(autouse=True)
def no_external_credentials_in_tests(monkeypatch):
    """Only scripts/verify_live.py may use the developer's actual provider keys."""
    monkeypatch.setenv('LANGSMITH_TRACING','false')
    monkeypatch.delenv('OPENROUTER_API_KEY',raising=False)

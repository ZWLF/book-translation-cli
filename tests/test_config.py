from pathlib import Path

import pytest
from pydantic import ValidationError

from booksmith.config import PublishingRunConfig, RunConfig
from booksmith.provider_catalog import get_provider_option


def test_resolved_api_key_falls_back_to_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    (tmp_path / ".env").write_text("GEMINI_API_KEY=test-dotenv-key\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = RunConfig(provider="gemini", model="gemini-3.1-flash-lite-preview")

    assert config.resolved_api_key() == "test-dotenv-key"


def test_run_config_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError, match="Unsupported provider: zhipu"):
        RunConfig(provider="zhipu", model="glm-4-flash")


def test_run_config_rejects_mixed_case_provider_alias() -> None:
    with pytest.raises(ValidationError, match="Unsupported provider: OpenAI"):
        RunConfig(provider="OpenAI", model="gpt-4o-mini")


@pytest.mark.parametrize(
    ("provider", "model", "expected_message"),
    [
        ("openai", "gemini-3.1-flash-lite-preview", "Unsupported model for provider openai"),
        ("gemini", "gpt-4o-mini", "Unsupported model for provider gemini"),
    ],
)
def test_run_config_rejects_invalid_provider_model_pairs(
    provider: str,
    model: str,
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        RunConfig(provider=provider, model=model)


def test_run_config_uses_catalog_default_model_and_api_key_env() -> None:
    config = RunConfig(provider="gemini")
    option = get_provider_option("gemini")

    assert config.resolved_model() == option.default_model
    assert config.resolved_api_key_env() == option.api_key_env


@pytest.mark.parametrize(
    ("config_type", "provider"),
    [
        (RunConfig, "openai"),
        (PublishingRunConfig, "gemini"),
    ],
)
def test_blank_model_falls_back_to_provider_default(config_type: type, provider: str) -> None:
    config = config_type(provider=provider, model="")
    option = get_provider_option(provider)

    assert config.resolved_model() == option.default_model


def test_publishing_run_config_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError, match="Unsupported provider: zhipu"):
        PublishingRunConfig(provider="zhipu", model="glm-4-flash")


@pytest.mark.parametrize(
    ("provider", "model", "expected_message"),
    [
        ("openai", "gemini-3.1-flash-lite-preview", "Unsupported model for provider openai"),
        ("gemini", "gpt-4o-mini", "Unsupported model for provider gemini"),
    ],
)
def test_publishing_run_config_rejects_invalid_provider_model_pairs(
    provider: str,
    model: str,
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        PublishingRunConfig(provider=provider, model=model)

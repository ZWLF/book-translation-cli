from booksmith.provider_catalog import (
    DEFAULT_PROVIDER_ID,
    get_provider_option,
    list_enabled_provider_options,
)


def test_enabled_provider_catalog_only_exposes_supported_runtime_providers() -> None:
    options = list_enabled_provider_options()

    assert [option.provider_id for option in options] == ["openai", "gemini"]
    assert options[0].display_label == "OpenAI / GPT 模型"
    assert options[1].display_label == "Gemini / 谷歌 Gemini"


def test_provider_option_exposes_default_model_and_env_key() -> None:
    option = get_provider_option("gemini")

    assert option.default_model == "gemini-3.1-flash-lite-preview"
    assert option.api_key_env == "GEMINI_API_KEY"
    assert option.models == ("gemini-3.1-flash-lite-preview", "gemini-2.5-flash-lite")


def test_provider_option_rejects_mixed_case_aliases() -> None:
    try:
        get_provider_option("OpenAI")
    except ValueError as exc:
        assert str(exc) == "Unsupported provider: OpenAI"
    else:
        raise AssertionError("expected ValueError for mixed-case provider alias")


def test_default_provider_id_matches_catalog() -> None:
    default_option = get_provider_option(DEFAULT_PROVIDER_ID)

    assert DEFAULT_PROVIDER_ID == "openai"
    assert default_option.enabled is True
    assert default_option.provider_id == DEFAULT_PROVIDER_ID
    assert default_option in list_enabled_provider_options()

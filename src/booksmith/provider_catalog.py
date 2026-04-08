from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderOption:
    provider_id: str
    display_label: str
    api_key_env: str
    models: tuple[str, ...]
    default_model: str
    enabled: bool = True


PROVIDER_OPTIONS: tuple[ProviderOption, ...] = (
    ProviderOption(
        provider_id="openai",
        display_label="OpenAI / GPT \u6a21\u578b",
        api_key_env="OPENAI_API_KEY",
        models=("gpt-4o-mini", "gpt-4.1-mini"),
        default_model="gpt-4o-mini",
    ),
    ProviderOption(
        provider_id="gemini",
        display_label="Gemini / \u8c37\u6b4c Gemini",
        api_key_env="GEMINI_API_KEY",
        models=("gemini-3.1-flash-lite-preview", "gemini-2.5-flash-lite"),
        default_model="gemini-3.1-flash-lite-preview",
    ),
)

DEFAULT_PROVIDER_ID = "openai"

def list_enabled_provider_options() -> tuple[ProviderOption, ...]:
    return tuple(option for option in PROVIDER_OPTIONS if option.enabled)


def get_default_provider_option() -> ProviderOption:
    return get_provider_option(DEFAULT_PROVIDER_ID)


def get_provider_option(provider_id: str) -> ProviderOption:
    for option in PROVIDER_OPTIONS:
        if option.provider_id == provider_id and option.enabled:
            return option
    raise ValueError(f"Unsupported provider: {provider_id}")

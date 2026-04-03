import pytest
from pydantic import ValidationError

from book_translator.config import PublishingRunConfig


def test_publishing_run_config_defaults() -> None:
    config = PublishingRunConfig()

    assert config.style == "non-fiction-publishing"
    assert config.from_stage == "draft"
    assert config.to_stage == "final-review"
    assert config.mode == "publishing"
    assert config.max_concurrency == 3


def test_publishing_run_config_rejects_invalid_stage_and_mode() -> None:
    with pytest.raises(ValidationError):
        PublishingRunConfig(
            style="non-fiction-publishing",
            from_stage="outline",
            to_stage="final-review",
            mode="publishing",
            max_concurrency=3,
        )


def test_publishing_run_config_rejects_invalid_mode() -> None:
    with pytest.raises(ValidationError):
        PublishingRunConfig(mode="engineering")


def test_publishing_run_config_rejects_invalid_max_concurrency() -> None:
    with pytest.raises(ValidationError):
        PublishingRunConfig(max_concurrency=0)


def test_publishing_run_config_rejects_upper_bound_max_concurrency() -> None:
    with pytest.raises(ValidationError):
        PublishingRunConfig(max_concurrency=17)

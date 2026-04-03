from book_translator.config import PublishingRunConfig


def test_publishing_run_config_defaults() -> None:
    config = PublishingRunConfig()

    assert config.style == "non-fiction-publishing"
    assert config.from_stage == "draft"
    assert config.to_stage == "final-review"
    assert config.mode == "publishing"
    assert config.max_concurrency == 3

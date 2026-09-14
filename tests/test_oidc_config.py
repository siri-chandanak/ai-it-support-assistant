from ai_it_support_assistant.core.config import Settings


def test_oidc_algorithm_list() -> None:
    settings = Settings(
        oidc_algorithms="RS256, RS384",
    )

    assert settings.oidc_algorithm_list == [
        "RS256",
        "RS384",
    ]

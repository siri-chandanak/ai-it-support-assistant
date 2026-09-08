import pytest

from ai_it_support_assistant.services.live_status_service import (
    ServiceNotFoundError,
    get_live_service_status,
)


def test_known_service_returns_status() -> None:
    result = get_live_service_status(service_name="vpn-gateway")

    assert result.service_name == "vpn-gateway"
    assert result.status == "degraded"


def test_service_name_is_normalized() -> None:
    result = get_live_service_status(service_name=" VPN-GATEWAY ")

    assert result.service_name == "vpn-gateway"


def test_unknown_service_raises() -> None:
    with pytest.raises(ServiceNotFoundError):
        get_live_service_status(service_name="does-not-exist")

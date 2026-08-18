from __future__ import annotations

from industrial_agents.config import Settings
from industrial_agents.domain.security import create_token, decode_token, hash_password, verify_password


def test_password_and_token_round_trip() -> None:
    settings = Settings(jwt_secret="test-secret-with-at-least-thirty-two-characters")
    encoded = hash_password("SafePassword123!")
    assert verify_password("SafePassword123!", encoded)
    assert not verify_password("wrong-password", encoded)
    token = create_token(
        subject="user-1",
        role="engineer",
        tenant_id="tenant-1",
        token_type="access",
        settings=settings,
        session_id="session-1",
    )
    assert decode_token(token, settings)["sub"] == "user-1"

from services.media_tokens import mint_media_access_token, verify_media_access_token


def test_media_access_token_round_trip() -> None:
    token, expires_at = mint_media_access_token(
        "media-123",
        fleet_id="fleet-1",
        user_id="user-1",
    )
    assert expires_at > 0
    assert verify_media_access_token("media-123", token) is True
    assert verify_media_access_token("other-media", token) is False

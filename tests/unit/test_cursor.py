import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.api.v1.cursor import decode_cursor, encode_cursor


def test_cursor_round_trip() -> None:
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    item_id = uuid.uuid4()

    cursor = encode_cursor(created_at, item_id)
    decoded_created_at, decoded_id = decode_cursor(cursor)

    assert decoded_created_at == created_at
    assert decoded_id == item_id


def test_malformed_cursor_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        decode_cursor("not-a-valid-cursor!!!")

    assert exc_info.value.status_code == 422

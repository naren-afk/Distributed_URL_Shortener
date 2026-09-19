import pytest
from app.services.base62 import decode, encode, id_to_short_code


def test_base62_encode_decode():
    numbers = [0, 1, 61, 62, 125, 999999, 10_000_000, 3_500_000_000]
    for num in numbers:
        encoded = encode(num)
        assert isinstance(encoded, str)
        decoded = decode(encoded)
        assert decoded == num, f"Mismatch for number {num}: got {decoded}"


def test_base62_negative_error():
    with pytest.raises(ValueError, match="Cannot encode negative"):
        encode(-5)


def test_base62_invalid_char():
    with pytest.raises(ValueError, match="Invalid Base62 character"):
        decode("invalid#char")


def test_id_to_short_code():
    code1 = id_to_short_code(1)
    code2 = id_to_short_code(2)
    assert code1 != code2
    assert len(code1) >= 4

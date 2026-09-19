BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(BASE62_ALPHABET)  # 62

# Start at an offset so short codes start with clean 6-character lengths rather than 1-char
MIN_ID_OFFSET = 10_000_000


def encode(num: int) -> str:
    """Encode an integer to a Base62 string."""
    if num < 0:
        raise ValueError("Cannot encode negative numbers to Base62")
    if num == 0:
        return BASE62_ALPHABET[0]

    digits = []
    while num > 0:
        digits.append(BASE62_ALPHABET[num % BASE])
        num //= BASE
    return "".join(reversed(digits))


def decode(s: str) -> int:
    """Decode a Base62 string back to an integer."""
    num = 0
    for char in s:
        idx = BASE62_ALPHABET.find(char)
        if idx == -1:
            raise ValueError(f"Invalid Base62 character: {char}")
        num = num * BASE + idx
    return num


def id_to_short_code(db_id: int) -> str:
    """Encodes database auto-increment ID with offset into a short code."""
    return encode(db_id + MIN_ID_OFFSET)

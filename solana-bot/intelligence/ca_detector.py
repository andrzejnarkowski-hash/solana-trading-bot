import re

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

CA_PATTERN = re.compile(
    r"(?<![1-9A-HJ-NP-Za-km-z])"
    r"[1-9A-HJ-NP-Za-km-z]{32,44}"
    r"(?![1-9A-HJ-NP-Za-km-z])"
)


def is_valid_solana_address(address):
    number = 0

    for char in address:
        if char not in BASE58_ALPHABET:
            return False

        number = number * 58 + BASE58_ALPHABET.index(char)

    decoded = number.to_bytes(
        (number.bit_length() + 7) // 8,
        "big"
    )

    leading_zeros = len(address) - len(address.lstrip("1"))
    decoded = b"\x00" * leading_zeros + decoded

    return len(decoded) == 32


def extract_addresses(text):
    if not isinstance(text, str):
        return []

    candidates = CA_PATTERN.findall(text)

    return list(dict.fromkeys(
        address for address in candidates
        if is_valid_solana_address(address)
    ))


if __name__ == "__main__":
    sample = (
        "New token just launched! CA: "
        "DigVnUDwgbSSWNMNsgzGNw8EQhqwjniPU2EsfD4Wpump"
    )

    print("Detected CAs:", extract_addresses(sample))

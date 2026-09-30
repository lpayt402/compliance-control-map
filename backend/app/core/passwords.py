import unicodedata

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 128

# A deliberately small offline floor for the self-hosted MVP. Larger organization-specific
# blocklists can be added later without changing the hashing or authentication contract.
COMMON_PASSWORDS = frozenset(
    {
        "123456789012345",
        "letmeinletmein",
        "passwordpassword",
        "qwertyqwertyqwerty",
        "welcome123456789",
    }
)

PASSWORD_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19 * 1024,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


class PasswordPolicyError(ValueError):
    pass


def normalize_password(password: str) -> str:
    return unicodedata.normalize("NFC", password)


def validate_password(password: str) -> str:
    normalized = normalize_password(password)
    if len(normalized) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(normalized) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters.")
    if normalized.casefold() in COMMON_PASSWORDS:
        raise PasswordPolicyError("Password is too commonly used.")
    return normalized


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(validate_password(password))


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(encoded_hash, normalize_password(password))
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def password_needs_rehash(encoded_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.check_needs_rehash(encoded_hash)
    except InvalidHashError:
        return False

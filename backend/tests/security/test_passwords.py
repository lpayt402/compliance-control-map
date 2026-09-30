import pytest

from app.core.passwords import PasswordPolicyError, hash_password, verify_password


def test_passwords_use_argon2id_and_verify_without_storing_plaintext() -> None:
    candidate = "a long local passphrase"

    encoded = hash_password(candidate)

    assert encoded.startswith("$argon2id$")
    assert candidate not in encoded
    assert verify_password(candidate, encoded) is True
    assert verify_password("this is not the password", encoded) is False


def test_password_policy_rejects_short_and_common_passwords() -> None:
    with pytest.raises(PasswordPolicyError, match="at least 15"):
        hash_password("fourteen-chars")

    with pytest.raises(PasswordPolicyError, match="commonly used"):
        hash_password("passwordpassword")


def test_password_policy_accepts_at_least_sixty_four_characters() -> None:
    password = "a" * 64

    assert verify_password(password, hash_password(password)) is True

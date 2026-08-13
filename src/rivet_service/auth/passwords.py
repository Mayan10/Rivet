"""Argon2id password hashing (docs/saas-buildout.md section 11: "Argon2id
for passwords, never SHA/bcrypt-with-defaults"). ``argon2-cffi``'s
default parameters already target argon2id with modern OWASP-recommended
cost settings -- not overridden here.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, VerificationError):
        return False

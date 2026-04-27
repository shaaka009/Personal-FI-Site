from datetime import datetime, timedelta, timezone
from base64 import urlsafe_b64encode
from hashlib import sha256
from cryptography.fernet import Fernet
from jose import jwt
from passlib.context import CryptContext
from app.config import settings

# Use PBKDF2-SHA256 to avoid bcrypt backend/version issues and
# bcrypt's 72-byte password limitation.
pwd_context = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')


def _derive_key() -> bytes:
    return urlsafe_b64encode(sha256(settings.master_key.encode()).digest())


def encrypt_secret(value: str) -> str:
    return Fernet(_derive_key()).encrypt(value.encode()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_exp_minutes)
    return jwt.encode({'sub': subject, 'exp': exp}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

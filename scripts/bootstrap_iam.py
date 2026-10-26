#!/usr/bin/env python3
"""Create IAM environment values without writing secrets to the repository."""

from getpass import getpass
from pathlib import Path
import sys
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from security import IAMService, generate_totp_secret, hash_password


def main():
    username = input('IAM admin username: ').strip()
    normalized = IAMService._normalize_username(username)
    if not normalized:
        raise SystemExit('Username must be 3-64 ASCII characters and may contain . _ @ + -')

    password = getpass('Password (minimum 8 characters): ')
    confirmation = getpass('Confirm password: ')
    if password != confirmation:
        raise SystemExit('Passwords do not match')
    if len(password) < 8:
        raise SystemExit('Password is too short')

    secret = generate_totp_secret()
    issuer = 'Ezwatek'
    otp_uri = f'otpauth://totp/{quote(issuer + ":" + normalized)}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30'

    print('\nCopy these values into a secret manager or protected environment, never into Git:\n')
    print(f'export IAM_ADMIN_USERNAME={normalized}')
    print(f'export IAM_ADMIN_PASSWORD_HASH={hash_password(password)}')
    print(f'export IAM_MFA_TOTP_SECRET={secret}')
    print('export IAM_ADMIN_ROLES=owner')
    print('\nAdd this URI to an authenticator app:')
    print(otp_uri)
    print('\nUse the generated six-digit code as MFA_CODE during login.')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Create a Secrets Manager secret holding a new random password, without ever printing the password.

Usage:  python3 scripts/new_secret.py <secret-name>
The password is 24 characters: upper + lower + digits + '-' and '_' (meets Active Directory complexity
rules and contains nothing a shell or an SMB credentials file would misread). Prints only the ARN.
"""
import secrets, string, sys
from kit_aws import aws

name = sys.argv[1]
alphabet = string.ascii_letters + string.digits
while True:
    pw = "".join(secrets.choice(alphabet) for _ in range(20)) + secrets.choice("-_") + secrets.choice(string.digits) \
         + secrets.choice(string.ascii_uppercase) + secrets.choice(string.ascii_lowercase)
    if any(c.isupper() for c in pw) and any(c.islower() for c in pw) and any(c.isdigit() for c in pw):
        break
arn = aws("secretsmanager", "create-secret", "--name", name, "--secret-string", pw,
          "--description", "Shared storage lab - AD password (generated, never displayed)")["ARN"]
print(arn)

# ADR 0006: Generated secrets and no inbound access

**Status:** Accepted
**Context:** This build has three directory passwords and four instances. Every one of them is a way in if it's handled carelessly.

## Decision

| Concern | Control |
|---|---|
| Directory passwords | [`new_secret.py`](../../scripts/new_secret.py) generates 24-character passwords straight into Secrets Manager and prints only the ARN |
| Who reads them | Linux clients: the two test users' secrets only. Windows admin server: the Admin secret only |
| Using them | Read inside the command that needs them (`$(aws secretsmanager get-secret-value …)`), or by the tool into a root-only file deleted after the mount |
| Shell access | Session Manager for Linux, SSM Run Command for Windows; no key pairs, no inbound rules |
| Instance metadata | IMDSv2 required on every instance |
| Storage access | Each storage service's security group admits only the clients' group, on that service's ports |

## Consequences

- No password appeared on screen, in `env.sh` or in shell history at any point in the build.
- Teardown deletes the secrets with `--force-delete-without-recovery`, so nothing lingers in a recovery window.
- The clients still have outbound internet for package installs. VPC endpoints would remove that (see `aws-private-connectivity-endpoints`).

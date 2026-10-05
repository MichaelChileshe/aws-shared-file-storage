# ADR 0005: FSx for Lustre Scratch 2 linked to S3, created per run

**Status:** Accepted
**Context:** Themba's actuarial dataset lives in S3. The models need fast, shared, POSIX access to it for a few days a quarter.

## Options considered

| Option | Verdict |
|---|---|
| Copy the dataset to each machine | ❌ Slow, and personal data ends up on many disks |
| EFS | ⚠️ Shared and fast for large files, but no S3 link: the data would have to be copied in and kept in sync |
| FSx for Lustre Persistent | ⚠️ Replicated and durable, but paid for all month for a job that runs a few days a quarter |
| **FSx for Lustre Scratch 2 with an S3 import path** | ✅ Chosen |

## Decision

Scratch 2, 1.2 TiB, **Lustre 2.15** (matching the Amazon Linux 2023 client), `ImportPath=s3://…/actuarial`, created for the run and deleted after it.

## Consequences

- Files visible immediately; first read 20.1 MB/s from S3, second read 252.4 MB/s from Lustre (12.6×).
- Scratch isn't replicated: results must go back to S3 before the file system is deleted.
- About US$11 per two-day run, against about US$168 a month if left running.

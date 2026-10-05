# ADR 0001: Choose shared storage per workload, not one service for everything

**Status:** Accepted
**Context:** Three clients each asked for "a shared drive". Their workloads differ: Linux web servers sharing assets, Windows users needing AD permissions, and compute jobs reading a large S3 dataset. One service for all three would be wrong for at least two of them.

## Options considered

| Option | Verdict |
|---|---|
| EFS for everyone | ❌ Kgotla's users and permissions live in Active Directory and speak SMB; EFS is NFS for Linux |
| FSx for Windows for everyone | ❌ Ubuntu Retail's Linux web servers would need SMB clients and AD accounts; no S3 link for Themba |
| EBS volumes copied around | ❌ One instance, one AZ: the problem Ubuntu Retail already has |
| S3 as a "drive" | ❌ Object storage: no locking, no in-place edits, no NTFS permissions |
| **EFS for Ubuntu Retail, FSx for Windows for Kgotla, FSx for Lustre for Themba** | ✅ Chosen |

## Decision

One service per workload, each built with its own access model and measured with the same benchmark, so the choice can be defended with numbers.

## Consequences

- Measured on one client: EFS 534/531 MB/s, Lustre 581/617 MB/s, FSx for Windows 90/286 MB/s, against local EBS at 148/137 MB/s. EFS created small files about 200× more slowly than EBS, which rules it out for small-file-heavy workloads.
- Each client's permissions model matches how their team already works: POSIX ownership (EFS), AD groups and NTFS (FSx for Windows), the instance role and VPC (Lustre).
- Three services to operate instead of one. That's the price of each being right for its job.

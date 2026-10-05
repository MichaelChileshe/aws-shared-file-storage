# ADR 0003: FSx for Windows File Server joined to AWS Managed Microsoft AD

**Status:** Accepted
**Context:** Kgotla's back office uses Windows, mapped drives and folder permissions. The requirement is that access is decided by who someone is in the directory, and that it can be audited.

## Options considered

| Option | Verdict |
|---|---|
| Windows Server on EC2 with a file share | ⚠️ Works, but patching, backups, disk growth and failover are all ours |
| EFS with SMB clients | ❌ EFS is NFS only |
| FSx for Windows with a self-managed AD | ⚠️ Right for a company with an existing on-prem AD; Kgotla needs one first |
| **FSx for Windows + AWS Managed Microsoft AD** | ✅ Chosen |

## Decision

- Directory: AWS Managed Microsoft AD, Standard, two domain controllers in two AZs.
- File system: Single-AZ 2, 32 GiB SSD, 32 MB/s for the lab; **Multi-AZ in production**.
- Clients connect over **SMB 3.1.1 with encryption**.

## Consequences

- Access decided by AD: Finance-Team member allowed, non-member denied, wrong password refused, all tested from a Linux client.
- The directory costs about as much as the small file system and takes the longest to create. It also becomes Kgotla's sign-in for everything else joined to it.
- AD DNS names don't resolve through the VPC resolver, so the lab's Linux clients used the file server's IP. Production adds a Route 53 Resolver forwarding rule for `corp.kgotla.internal`.

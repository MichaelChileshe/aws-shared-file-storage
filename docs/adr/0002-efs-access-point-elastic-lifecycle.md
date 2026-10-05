# ADR 0002: EFS with an access point, Elastic throughput and a lifecycle policy

**Status:** Accepted
**Context:** Ubuntu Retail's web servers must see the same files in every AZ. Files are written by different servers and processes, and most campaign assets go cold after a few weeks.

## Decision

| Setting | Choice | Alternative rejected |
|---|---|---|
| Throughput mode | **Elastic** | Bursting (credits run out under sustained load); Provisioned (paying for headroom all month) |
| Identity | **Access point**: uid/gid 1001, root `/design` | Relying on each server's local users having matching IDs |
| Lifecycle | **IA after 30 days, back on first access** | No lifecycle (cold files billed at Standard forever) |
| Encryption | At rest + **TLS** mounts | Plain NFS inside the VPC |
| Mount targets | One per AZ the clients use | A single mount target (cross-AZ traffic, and DNS resolves only in AZs that have one) |

## Consequences

- A file written as root on web-a showed as `1001 1001` on both servers. Ownership no longer depends on who wrote the file.
- Large-file throughput (534/531 MB/s) beat local gp3; small-file creation (96/s) is the trade-off, documented for the web team.
- The trap drill showed what a missing mount target looks like (an instant DNS failure), so adding an AZ to the web tier now includes "add a mount target" in its checklist.

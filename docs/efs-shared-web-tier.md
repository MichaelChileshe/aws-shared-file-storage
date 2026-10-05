# EFS for Ubuntu Retail's web tier, and the two ways it fails to mount

## The scenario

Ubuntu Retail's product photos and campaign files lived on one web server's disk. Behind a load balancer, half the requests went to the other server, which didn't have the files, so customers saw broken images until a designer copied them across by hand. It was the classic shared-state problem in a scaled-out web tier.

## What I built

| Piece | Setting | Why |
|---|---|---|
| File system `urg-design-files` | Encrypted, General Purpose, **Elastic throughput** | Throughput follows the workload; no burst credits to run out of |
| Lifecycle | **Infrequent Access after 30 days**, back to Standard on first access | Last season's campaign files cost a fraction per GB |
| Mount targets | **1a and 1b** (1c added during the drill) | A mount target per AZ the clients live in |
| Access point `urg-design-ap` | POSIX user **1001:1001**, root directory `/design` (created 0775) | Every server sees the same tree and writes files with the same owner |
| Security group | NFS 2049 from the clients' security group only | Nothing else in the VPC can mount it |
| Client mounts | `mount -t efs -o tls,accesspoint=...` (amazon-efs-utils) | NFS 4.1 inside TLS |

## Two web servers, one file system ([`13`](screenshots/13-step6-web-a-mounts-and-writes.png)–[`15`](screenshots/15-step6-ebs-and-efs-benchmarks.png))

1. On **web-a** (us-east-1a), as root: `Spring campaign brief v1 - written on ip-10-70-1-205.ec2.internal`.
2. `ls -ln` showed the file owned by **1001 1001**, not root (0 0). The access point rewrote the identity.
3. On **web-b** (us-east-1b), through its own AZ's mount target: read the line and appended `approved by web-b at 09:28:33 UTC`.
4. Back on web-a: both lines.

That's Ubuntu Retail's broken-images problem solved at the storage layer. Any number of web servers in any AZ with a mount target sees the same files immediately.

## The trap drill ([`16`](screenshots/16-step7-drill-no-mount-target-dns-fails.png)–[`22`](screenshots/22-step7-drill-mounted-again.png))

From `storage-client-c` in **us-east-1c**, where the file system had no mount target, I ran `fstool nfs-test`. It does a plain NFS mount by the file system's DNS name, limited to 25 seconds.

| # | Situation | What the client saw | Time |
|---|---|---|---|
| 1 | No mount target in 1c | `getent hosts` returned nothing; `mount.nfs: Failed to resolve server fs-….efs.us-east-1.amazonaws.com: Name or service not known` | **0.0 s** |
| – | Created a mount target in 1c | First retry still failed to resolve (DNS not yet propagated); the next resolved **10.70.3.99** and mounted | 0.5 s |
| 2 | Revoked TCP 2049 from the EFS security group | Name resolved fine, then silence: **TIMED OUT after 25 s** | 25 s |
| – | Restored the rule | Mounted | 0.2 s |

**How to tell them apart in a real incident:**

- **"Name or service not known" straight away** → a DNS problem. Either no mount target in the client's AZ, or the VPC doesn't have DNS hostnames/DNS support enabled. The EFS DNS name resolves to the mount target **in the client's own AZ**, and only if one exists.
- **A hang that ends in a timeout** → the name resolved and packets went out, but nothing answered. A security group or NACL is dropping TCP 2049. A security group never sends a "refused"; it just drops.

When the 1c mount target was first created, the mount still failed to resolve for a short time. AWS documents up to 90 seconds before a new mount target's DNS record is available, so a failure in that window isn't a verdict: wait, and retry if it still fails.

## Throughput: what EFS is good and bad at ([`15`](screenshots/15-step6-ebs-and-efs-benchmarks.png))

| | Sequential write | Sequential read | 4 KiB files created/s | 4 KiB files read/s |
|---|---|---|---|---|
| EBS gp3 (local root disk) | 148.2 MB/s | 137.1 MB/s | 18,803 | 3,837 |
| **EFS** (Elastic, TLS) | **533.7 MB/s** | **530.8 MB/s** | **96** | **197** |

- **Large files: EFS beat the local gp3 disk 3.6×.** gp3's default 125 MB/s baseline is the limit there, while EFS Elastic spreads I/O across many servers. Product photos and campaign assets are exactly this shape.
- **Small files: EFS was about 200× slower than local disk.** Each create is a network round trip with NFS's consistency guarantees, plus TLS. That's the reason not to put build directories, `node_modules`, PHP sessions or anything that writes thousands of tiny files a second on EFS.

# Benchmarks: one test, four targets

## Method

All four runs came from the same client, `storage-client-a` (t3.medium, Amazon Linux 2023, us-east-1a), using [`fstool bench`](../client/fstool.py):

1. **Sequential write**: `fio`, 4 jobs × 256 MiB, 1 MiB blocks, `psync`, with a final `fsync`, so the time includes getting the data to storage.
2. **Sequential read**: page cache dropped (`echo 3 > /proc/sys/vm/drop_caches`), then the same files read back.
3. **Small files**: 1,000 × 4 KiB files created (then `sync`), page cache dropped, then read back.

Results were appended to `/opt/fstool/results.csv` and printed with `fstool results` ([`35`](screenshots/35-step12-smb-benchmark-and-results.png)).

## Results

| Target | Write MB/s | Read MB/s | 4 KiB created/s | 4 KiB read/s |
|---|---|---|---|---|
| EBS gp3 (root disk, baseline) | 148.2 | 137.1 | 18,803 | 3,837 |
| EFS (Elastic, TLS, access point) | 533.7 | 530.8 | 96 | 197 |
| FSx for Lustre (Scratch 2, 1.2 TiB) | 581.0 | 616.7 | 488 | 728 |
| FSx for Windows (32 MB/s, SMB 3.1.1 sealed) | 89.5 | 285.9 | 865 | 1,049 |

## How to read them

- **EBS gp3** sits at its default baseline of 125 MB/s plus a little. It's the only target with no network hop per operation, which is why it wins small files by two orders of magnitude.
- **EFS and Lustre** both landed around 530–620 MB/s, which is close to 5 Gbps: the burst network ceiling of a t3.medium. At that point the **client** is the limit. Both services scale well beyond one client, so these numbers are a floor, not their maximum.
- **EFS small files (96/s)** shows the cost of a network file system with strong consistency, plus TLS: every create is a round trip. Fine for images and documents; wrong for workloads that churn thousands of tiny files.
- **FSx for Windows** wrote at 89.5 MB/s and read at 285.9 MB/s from a file system provisioned at 32 MB/s. Small FSx for Windows file systems can burst above their baseline for a while; a long copy would settle back towards 32 MB/s. For Kgotla's office documents, the small-file rates (865 / 1,049 per second) matter more, and they're the best of the three network file systems.
- **Lustre's 616.7 MB/s read** was measured after the dataset had been hydrated. The cold first read from S3 ran at 20.1 MB/s ([`lustre-over-s3.md`](lustre-over-s3.md)).

## What I'd change for a production benchmark

- Several clients in parallel, on network-optimised instances, to find each service's limit rather than the client's.
- Longer runs (minutes, not one GiB), to get past burst behaviour on FSx for Windows and EBS.
- Latency percentiles (`fio --lat_percentiles`) alongside throughput, since interactive users feel latency first.

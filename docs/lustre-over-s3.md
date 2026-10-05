# FSx for Lustre over S3: Themba's actuarial scratch space

## The scenario

Every quarter Themba's actuaries copy the policy-experience dataset from S3 to their machines, wait, run their models, and then have copies of personal data scattered across laptops. They need fast shared storage over the S3 data, only for the days the models run.

## What I built

| Piece | Setting | Why |
|---|---|---|
| Dataset | `s3://themba-actuarial-<account>/actuarial/`, 32 × 32 MiB CSV (1.0 GiB), private, encrypted | Synthetic policy rows: product, age, sum assured, premium, claims |
| File system `themba-actuarial-scratch` | **Scratch 2**, 1,200 GiB (the minimum), **Lustre 2.15**, in 1a | Cheapest Lustre, no replication: built for a job, deleted after it |
| S3 link | `ImportPath=s3://…/actuarial` | Objects appear as files immediately; data loads on first read |
| Security groups | Lustre SG: 988 and 1018–1023 from the clients **and from itself**; clients' SG: the same ports from the Lustre SG | What the FSx for Lustre documentation specifies for servers and clients |

**Why 2.15:** Amazon Linux 2023 ships the Lustre 2.15 client, and a 2.15 client refuses to connect to a 2.10 file system. 2.10 is the default for Scratch deployments, so I set `--file-system-type-version 2.15` when creating it ([`24`](screenshots/24-step8-lustre-scratch2-available.png)).

## Lazy loading, measured ([`25`](screenshots/25-step9-lustre-lazy-load-hydration.png))

The objects appeared under `/mnt/lustre/actuarial/`, with the S3 prefix kept as a directory, as soon as the file system mounted. Only the metadata had been imported.

| Moment | `lfs hsm_state` on a file | Read of all 32 files (1,073.7 MB) |
|---|---|---|
| Before the first read | `(0x0000000d) released exists archived`: listed, data still in S3 | – |
| **First read** | – | 53.5 s = **20.1 MB/s** (pulled from S3) |
| After it | `(0x00000009) exists archived`: no longer *released*, the data now lives on Lustre | – |
| **Second read** (page cache dropped first) | – | ≈4.25 s (shown rounded as 4.3 s) = **252.4 MB/s**, **12.6× faster** |

The first pass is the one-time cost of hydrating from S3. Every model run after that reads at Lustre speed. For a quarterly job that reads the same dataset dozens of times, the first pass is paid once.

## Throughput ([`26`](screenshots/26-step9-lustre-benchmark.png))

| | Sequential write | Sequential read | 4 KiB files created/s | 4 KiB files read/s |
|---|---|---|---|---|
| FSx for Lustre Scratch 2 | **581.0 MB/s** | **616.7 MB/s** | 488 | 728 |

The fastest large-file numbers in the test, from a single small client. A Lustre file system's throughput scales with its size and with the number of clients reading in parallel, which is how actuarial and ML clusters use it.

## In real use

- **Results go back to S3.** Scratch is not durable: if a file server fails, its data is gone. Model outputs belong in S3 (an export path, or a data repository task) before the file system is deleted.
- **Delete it after the run.** At 1.2 TiB minimum, Scratch 2 costs about US$168 a month if left running; for a two-day quarterly job it's closer to US$11.
- **No laptop copies.** The data stays in the VPC, on encrypted storage, readable by the instances that need it. That's the POPIA argument for this design, as much as the speed.

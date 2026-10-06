# Cost model

## What this build cost (estimate)

The directory, FSx for Windows and FSx for Lustre all bill **per hour while they exist**, so the build was planned to finish and tear down in one sitting. The directory was started first, because it takes longest to create.

| Item | Rate (us-east-1 list price, approx.) | Time alive | Approx. cost |
|---|---|---|---|
| AWS Managed Microsoft AD, Standard | ~US$0.12/hour (2 domain controllers) | ~2 hours | ~US$0.24 |
| FSx for Windows, 32 GiB SSD, 32 MB/s | ~US$0.10/hour | ~1 hour | ~US$0.10 |
| FSx for Lustre Scratch 2, 1,200 GiB | ~US$0.23/hour | ~1 hour | ~US$0.23 |
| EC2: Windows t3.medium + 3 Linux (t3.medium, 2 × t3.micro) | ~US$0.14/hour together | ~2 hours | ~US$0.28 |
| EFS Elastic: storage + ~2 GB written and read | per GB-month + per GB transferred | – | ~US$0.15 |
| S3 (1 GiB), Secrets Manager (3 secrets for a few hours) | – | – | cents |
| **Total** | | | **about US$1–2** |

Rates are approximate list prices; check the pricing pages for current figures. Cost Explorer refreshes at least once every 24 hours, so the final figure appears the next day.

## What Cost Explorer showed

The day after, Cost Explorer for **5–6 October 2026** ([`40`](screenshots/40-cost-explorer-oct-5-6.png)), grouped by service. The range is inclusive, so it covers the three builds I ran on 5 October (`aws-aurora-ha-architecture`, `aws-shared-file-storage` and `aws-hybrid-storage-transfer`), whatever had posted of 6 October (when I ran `aws-route53-routing-lab`), and the services that run in the account all the time:

| Service | Cost |
|---|---|
| Config (always on, from `aws-cloudtrail-config-governance`) | US$1.37 |
| EC2-Instances (all three builds) | US$0.90 |
| Relational Database Service (the Aurora build) | US$0.39 |
| FSx | US$0.18 |
| EC2-Other (EBS volumes, including the gateway's cache disk) | US$0.17 |
| Security Hub (always on) | US$0.12 |
| DataSync | US$0.10 |
| Elastic File System | US$0.09 |
| VPC | US$0.06 |
| Others | US$0.15 |
| **Total** | **US$3.53** |

This build's own lines are FSx (US$0.18) and Elastic File System (US$0.09), plus its share of EC2. Services without their own line (such as the directory) are in Others or not yet posted. Leaving out Config and Security Hub, which run whatever I build, everything else came to about **US$2.04**: mainly the three 5 October builds, plus whatever of 6 October had posted. That's well under my estimates for the three builds added together. Cost Explorer can still be catching up on the most recent day, so I treat this as a floor rather than a final bill.

## Price per GB is not the whole story

Approximate list prices, per GB-month:

| Storage | Per GB-month | What else you pay for |
|---|---|---|
| EBS gp3 | ~US$0.08 | Extra IOPS/throughput above the baseline |
| EFS Standard | ~US$0.30 | Per GB read/written (Elastic) |
| EFS Infrequent Access | ~US$0.016 | Per GB accessed |
| FSx for Windows, Single-AZ 2 SSD | ~US$0.13 | **~US$2.20 per MB/s of throughput capacity, per month**; the directory |
| FSx for Lustre, Scratch 2 | ~US$0.14 | **Minimum 1.2 TiB** |
| S3 Standard | ~US$0.023 | Requests |

The minimums dominate at small sizes:

| What I built | Monthly if left running | Effective cost per GB stored |
|---|---|---|
| FSx for Windows 32 GiB + 32 MB/s | ~US$4 storage + ~US$70 throughput ≈ **US$75** (+ ~US$88 for the directory) | ~US$2.30/GB |
| FSx for Lustre Scratch 2, 1.2 TiB | ≈ **US$168** whether it holds 1 GiB or 1,200 | ~US$168/GB at 1 GiB used |
| EFS with 1 GB of files | ≈ **US$0.30** + access charges | US$0.30/GB |

## At the clients' real sizes

- **Ubuntu Retail, 500 GB of design assets, 80% untouched after a month:** 100 GB Standard × US$0.30 + 400 GB IA × US$0.016 ≈ **US$36 a month** plus access charges. Without the lifecycle policy, the same 500 GB would be about US$150.
- **Kgotla, 1 TB of back-office files at 32 MB/s:** ~US$133 storage + ~US$70 throughput ≈ **US$200 a month**, plus the directory (~US$88), which also serves sign-in for everything else Kgotla joins to it. Multi-AZ for production roughly doubles the file system cost, and buys automatic failover.
- **Themba, quarterly two-day model runs on 1.2 TiB:** ~US$168 a month if left up, or about **US$11 per run** if created for the run and deleted after it, with the dataset staying in S3 at ~US$0.023/GB.

The pattern: **EFS** is cheap to start and expensive per GB if nothing moves to IA. **FSx for Windows** is dominated by throughput capacity, so size it to the workload. **Lustre Scratch** is cheap only if it's temporary.

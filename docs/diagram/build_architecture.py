#!/usr/bin/env python3
"""Regenerates docs/architecture.svg + docs/architecture.png using the OFFICIAL AWS Architecture Icons.

The icon pack is not committed (AWS licenses it for diagrams, not redistribution). Download it from
https://aws.amazon.com/architecture/icons/, unzip, then:

    AWS_ICONS_DIR=/path/to/unzipped-icon-package python3 build_architecture.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from awsdiag import Diagram, GREY, INK

NFS, SMB, LUS, DRILL, OK, AZ = "#7AA116", "#0073BB", "#8C4FFF", "#D13212", "#1D8102", "#00A4A6"
d = Diagram(1880, 1200)

d.text(40, 40, "Shared file storage, three ways: EFS, FSx for Windows File Server, FSx for Lustre", 19, "bold")
d.text(40, 64, "One workload per service, each measured with the same benchmark  ·  every rule SG-to-SG  ·  "
               "no inbound access, no typed passwords  ·  us-east-1", 13, "normal", GREY)

d.group("cloud", 20, 90, 1840, 1095, "AWS Cloud")
d.group("region", 40, 130, 1420, 1040, "us-east-1")
d.group("vpc", 60, 175, 1060, 975, "storage-lab-vpc  10.70.0.0/16  (DNS hostnames on)")

cols = [(80, "us-east-1a  ·  10.70.1.0/24"), (430, "us-east-1b  ·  10.70.2.0/24"), (780, "us-east-1c  ·  10.70.3.0/24")]
for x, name in cols:
    d.box(x, 215, 330, 915, AZ, fill="none")
    d.text(x + 12, 236, name, 12.5, "bold", AZ)


def node(key, x, y, title, l1="", l2="", color=INK, size=48):
    d.icon(key, x, y, size)
    d.text(x + size + 10, y + 16, title, 12.5, "bold", color)
    if l1:
        d.text(x + size + 10, y + 33, l1, 11, "normal", GREY)
    if l2:
        d.text(x + size + 10, y + 49, l2, 11, "normal", GREY)


# ---------------------------------------------------------------- clients (row 1)
d.text(102, 268, "UBUNTU RETAIL · web server 1", 11, "bold", NFS)
node("ec2_instance", 105, 280, "storage-client-a (web-a)", "t3.medium · the bench box", "mounts EFS, Lustre and SMB")
d.text(452, 268, "UBUNTU RETAIL · web server 2", 11, "bold", NFS)
node("ec2_instance", 455, 280, "storage-client-b (web-b)", "t3.micro", "reads web-a's files instantly")
d.text(802, 268, "TRAP DRILL", 11, "bold", DRILL)
node("ec2_instance", 805, 280, "storage-client-c", "t3.micro", "no mount target here (at first)", DRILL)

# ---------------------------------------------------------------- EFS band (row 2): mount targets on top, text below
d.raw('<rect x="100" y="430" width="1000" height="160" rx="6" fill="#F4F9EC" stroke="#7AA116" stroke-width="1.6"/>')
for x, label, c, dash in [(150, "mount target 10.70.1.94", NFS, False), (500, "mount target 10.70.2.187", NFS, False),
                          (850, "mount target 10.70.3.99", DRILL, True)]:
    d.box(x, 446, 220, 40, c, fill="#FFFFFF", dashed=dash, rx=4)
    d.text(x + 110, 471, label, 11.5, "bold", c, "middle")
d.text(960, 503, "added during the drill", 10.5, "normal", DRILL, "middle")
d.icon("efs", 114, 516, 52)
d.text(176, 534, "Amazon EFS  urg-design-files", 13.5, "bold", NFS)
d.text(176, 552, "encrypted · Elastic throughput · lifecycle: IA after 30 days, back on first access", 11.5,
       "normal", GREY)
d.text(176, 568, "access point urg-design-ap: /design, every file owned by uid/gid 1001 · NFS 4.1 over TLS",
       11.5, "normal", GREY)

d.line([(260, 340), (260, 444)], NFS, width=2.2)
d.line([(610, 340), (610, 444)], NFS, width=2.2)
d.line([(960, 340), (960, 444)], DRILL, dashed=True, width=2)
d.label(968, 380, "1) name won't resolve", DRILL, 10.5)
d.label(968, 402, "2) 2049 blocked: timeout", DRILL, 10.5)

# ---------------------------------------------------------------- Kgotla (row 3)
d.text(102, 628, "KGOTLA · back office", 11, "bold", SMB)
node("ec2_instance", 105, 640, "kgotla-admin", "Windows Server 2022, domain-joined", "managed over SSM only (no RDP)", SMB)
d.line([(129, 690), (129, 712)], SMB)
node("fsx_windows", 105, 714, "FSx for Windows File Server", "kgotla-backoffice · Single-AZ 2",
     "32 GiB SSD · 32 MB/s · SMB 3.1.1 sealed", SMB, 52)
d.box(105, 784, 290, 66, SMB, fill="#F0F6FC", rx=4)
d.text(115, 803, "\\share\\finance  NTFS:", 11.5, "bold", SMB)
d.text(115, 820, "Finance-Team Modify · inheritance removed", 11, "normal", INK)
d.text(115, 837, "thabo ✓   lerato ✗   wrong password ✗", 11, "bold", OK)

node("managed_ad", 105, 870, "Managed Microsoft AD", "corp.kgotla.internal (KGOTLA)", "DC 10.70.1.82", SMB)
node("managed_ad", 455, 870, "Managed Microsoft AD", "second domain controller", "DC 10.70.2.44", SMB)
d.line([(340, 893), (452, 893)], SMB, dashed=True, arrow=False)

# ---------------------------------------------------------------- Themba (row 4)
d.text(102, 958, "THEMBA · actuarial", 11, "bold", LUS)
node("fsx_lustre", 105, 970, "FSx for Lustre", "themba-actuarial-scratch · Scratch 2",
     "1.2 TiB · Lustre 2.15 · lazy load from S3", LUS, 52)

# client-a to Windows and Lustre, down the AZ's left margin
d.line([(105, 300), (92, 300), (92, 740), (103, 740)], SMB, width=2)
d.line([(105, 312), (86, 312), (86, 996), (103, 996)], LUS, width=2)

# ---------------------------------------------------------------- regional services
sx = 1140
d.icon("s3", sx, 972, 48)
d.text(sx + 58, 990, "S3  themba-actuarial-&lt;account&gt;", 12, "bold")
d.text(sx + 58, 1006, "actuarial/  32 x 32 MiB CSV (1.0 GiB)", 11, "normal", GREY)
d.text(sx + 58, 1021, "private, encrypted (SSE-S3)", 11, "normal", GREY)
d.line([(sx - 4, 1045), (300, 1045), (300, 1028)], LUS, dashed=True)
d.label(560, 1041, "import path: file list now, data pulled on first read", LUS, 10.5)

d.icon("secrets", sx, 220, 48)
d.text(sx + 58, 238, "Secrets Manager", 12.5, "bold")
d.text(sx + 58, 254, "kgotla/ad-admin, ad-thabo, ad-lerato", 11, "normal", GREY)
d.text(sx + 58, 269, "generated, never displayed", 11, "normal", GREY)

d.icon("ssm", sx, 310, 48)
d.text(sx + 58, 328, "Systems Manager", 12.5, "bold")
d.text(sx + 58, 344, "Session Manager shells (Linux)", 11, "normal", GREY)
d.text(sx + 58, 359, "Run Command: domain join + icacls", 11, "normal", GREY)

d.icon("directory_service", sx, 400, 48)
d.text(sx + 58, 418, "Directory Service Data API", 12.5, "bold")
d.text(sx + 58, 434, "users thabo, lerato; group", 11, "normal", GREY)
d.text(sx + 58, 449, "Finance-Team (thabo only), by CLI", 11, "normal", GREY)

d.icon("iam_role", sx + 4, 492, 40)
d.text(sx + 58, 506, "Two instance roles", 12.5, "bold")
d.text(sx + 58, 522, "clients: describe + 2 user secrets", 11, "normal", GREY)
d.text(sx + 58, 537, "admin: the AD Admin secret only", 11, "normal", GREY)

# ---------------------------------------------------------------- results + legend
bx, by = 1480, 130
d.box(bx, by, 365, 470, "#D5DBDB", fill="#fff", dashed=False)
d.text(bx + 14, by + 26, "Measured (same fio + small-file test)", 13, "bold")
d.text(bx + 14, by + 52, "MB/s write / read", 11.5, "bold", GREY)
rows = [("EBS gp3 (baseline)", "148 / 137", INK), ("EFS", "534 / 531", NFS),
        ("FSx for Lustre", "581 / 617", LUS), ("FSx for Windows", "90 / 286", SMB)]
for i, (n, v, c) in enumerate(rows):
    d.text(bx + 14, by + 76 + i * 22, n, 12, "bold", c)
    d.text(bx + 350, by + 76 + i * 22, v, 12, "normal", INK, "end")
d.text(bx + 14, by + 178, "4 KiB files created / read per second", 11.5, "bold", GREY)
rows = [("EBS gp3", "18,803 / 3,837", INK), ("EFS", "96 / 197", NFS),
        ("FSx for Lustre", "488 / 728", LUS), ("FSx for Windows", "865 / 1,049", SMB)]
for i, (n, v, c) in enumerate(rows):
    d.text(bx + 14, by + 202 + i * 22, n, 12, "bold", c)
    d.text(bx + 350, by + 202 + i * 22, v, 12, "normal", INK, "end")
d.text(bx + 14, by + 304, "Lustre over S3:", 12, "bold", LUS)
d.text(bx + 14, by + 324, "first read 20.1 MB/s (from S3)", 11.5)
d.text(bx + 14, by + 343, "second read 252.4 MB/s (12.6x)", 11.5)
d.text(bx + 14, by + 371, "Permissions:", 12, "bold", SMB)
d.text(bx + 14, by + 391, "member writes, non-member denied,", 11.5)
d.text(bx + 14, by + 410, "bad password refused (error 13)", 11.5)
d.text(bx + 14, by + 438, "Large-file numbers for EFS and Lustre sit", 10.5, "normal", GREY)
d.text(bx + 14, by + 454, "near the t3.medium client's network limit", 10.5, "normal", GREY)

lx, ly = 1480, 625
d.raw(f'<rect x="{lx}" y="{ly}" width="365" height="150" rx="4" fill="#fff" stroke="#D5DBDB"/>')
d.text(lx + 12, ly + 22, "Legend", 13, "bold")
leg = [(NFS, False, "NFS to EFS (TLS through the access point)"), (SMB, False, "SMB 3.1.1, encrypted, as an AD user"),
       (LUS, False, "Lustre client to FSx for Lustre"), (DRILL, True, "trap drill path")]
for i, (c, dash, t) in enumerate(leg):
    y = ly + 46 + i * 26
    d.line([(lx + 12, y), (lx + 58, y)], c, dashed=dash)
    d.text(lx + 66, y + 4, t, 11.5)

here = os.path.dirname(os.path.abspath(__file__))
d.save(os.path.join(here, "..", "architecture.svg"), os.path.join(here, "..", "architecture.png"))
print("wrote docs/architecture.svg and docs/architecture.png")

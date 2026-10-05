# FSx for Windows File Server with Active Directory: Kgotla's back office

## The scenario

Kgotla's finance team kept working papers on a file server under a desk. Anyone who knew `\\server\finance` could open it, and when the auditors asked who could read the reserving memos, nobody could answer. The team already thinks in Windows terms: user accounts, groups, mapped drives, folder permissions.

## What I built

| Piece | Setting |
|---|---|
| Directory | **AWS Managed Microsoft AD**, Standard, `corp.kgotla.internal` (NetBIOS `KGOTLA`), domain controllers in 1a (10.70.1.82) and 1b (10.70.2.44) |
| File system `kgotla-backoffice` | **Single-AZ 2**, 32 GiB SSD (the minimum), 32 MB/s throughput, joined to the directory, automatic backups off for the lab |
| Users and group | `thabo` and `lerato`; `Finance-Team` (Global, Security) containing **thabo only**, created with the **Directory Service Data API** (`aws ds-data`) |
| Passwords | Generated straight into Secrets Manager (`kgotla/ad-admin`, `ad-thabo`, `ad-lerato`) and passed into `reset-user-password` from the secret, never displayed |
| Admin server `kgotla-admin` | Windows Server 2022, **domain-joined through SSM** (`AWS-JoinDirectoryServiceDomain`), no RDP, no key pair |
| Folder permissions | `\share\finance`: explicit NTFS grants, then inheritance removed |

## Joining the domain without RDP ([`30`](screenshots/30-step10-admin-server-domain-joined.png))

[`scripts/ssm_run.py`](../scripts/ssm_run.py) waits for the instance to be Online in Systems Manager, sends the join document with the directory's ID, name and DNS IPs, and prints the result: `Domain join succeeded`, computer `EC2AMAZ-PT3RT5K`, in 62 seconds. A follow-up PowerShell query returned `Domain : corp.kgotla.internal`, `PartOfDomain : True`.

## Locking the finance folder ([`32`](screenshots/32-step11-ntfs-acl-finance-team-only.png))

A new FSx share gives **Authenticated Users read/write** and the delegated administrators group Full Control. That's Kgotla's "anyone who knows the path" problem again, now with authentication. [`windows/set-finance-acl.ps1.tpl`](../windows/set-finance-acl.ps1.tpl) runs on the admin server as SYSTEM through SSM Run Command:

1. Reads the AD Admin password from Secrets Manager through the server's role (which can read that one secret and nothing else).
2. Connects to `\\10.70.1.238\share` as `KGOTLA\Admin` and creates `finance\` with a README.
3. `icacls /grant`, first: SYSTEM Full Control (FSx requires SYSTEM to keep Full Control on every folder), AWS Delegated FSx Administrators Full Control, Admin Full Control, **Finance-Team Modify**, all inheriting to subfolders and files.
4. `icacls /inheritance:r`, second: removes the inherited entries, which is what drops Authenticated Users.

Grants go first so the folder is never left without an owner. The result had exactly four entries:

```
KGOTLA\Finance-Team:(OI)(CI)(M)
KGOTLA\Admin:(OI)(CI)(F)
KGOTLA\AWS Delegated FSx Administrators:(OI)(CI)(F)
NT AUTHORITY\SYSTEM:(OI)(CI)(F)
```

## Testing it from the user's side ([`33`](screenshots/33-step12-smb-mounts-and-bad-password.png), [`34`](screenshots/34-step12-thabo-allowed-lerato-denied.png))

From a Linux client, `fstool mount smb <user>` mounted the share over **SMB 3.1.1 with encryption (`seal`)**, with the password moved from Secrets Manager into a root-only credentials file that was deleted straight after the mount.

| Who | Action | Result |
|---|---|---|
| thabo (Finance-Team) | write `finance\q3-reserving-memo.txt`, list `finance\` | ✅ written; listing shows the README and the memo |
| lerato (not in the group) | list `finance\` | ❌ `Permission denied` |
| lerato | write a note at the share root | ✅ allowed: the lock is on the finance folder only, as designed |
| lerato with a wrong password | mount the share | ❌ `mount error(13): Permission denied` |

Three different outcomes, each decided by Active Directory: the group decides who's allowed, the folder ACL enforces it, and the directory refuses a bad credential before any file is touched.

## Design notes

- **Connecting by IP.** The Linux clients use the file server's IP (`PreferredFileServerIp`), because `corp.kgotla.internal` names don't resolve through the VPC's own DNS resolver. In production I'd add a Route 53 Resolver forwarding rule for the domain, so clients use the DNS name and Kerberos rather than NTLM.
- **Single-AZ 2 for the lab, Multi-AZ for production.** A finance file server people depend on all day should be Multi-AZ: a standby file server in a second AZ with automatic failover. Single-AZ was the honest choice for a one-afternoon test.
- **Backups.** Set to 0 days for the lab. Production would keep daily automatic backups and Windows shadow copies, so users can restore their own files.
- **Creation time.** The file system took about 30 minutes to create (created at 12:02 local time; the finance folder was written at 12:35). The directory is the other long wait, which is why I started it first and built EFS and Lustre while it came up. Both belong in a change plan.

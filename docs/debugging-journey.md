# Debugging journey

Seven things went wrong or nearly did. Each one is a situation I'd expect to meet again on real work.

---

## 1 · AWS refused the domain name

```
An error occurred (InvalidParameterException) when calling the CreateMicrosoftAD operation:
The following domain names are reserved and cannot be used with your directory: *.example, *.invalid, *.localhost
```

I'd picked `corp.kgotla.example`, thinking a reserved example domain was the safe choice for a lab. Directory Service rejects exactly those. I used **`corp.kgotla.internal`**: `.internal` is reserved for private networks and isn't on the blocked list ([`06`](screenshots/06-step2-managed-ad-creating.png)). Nothing had been created, and the Admin password secret was reused as it was.

**Lesson:** the domain name of a directory is close to permanent: changing it later means rebuilding. In production, use a subdomain of a domain the business owns (for example `corp.kgotla.co.za`), so names never collide with anything public.

---

## 2 · `cloud-init status` needed root

As `ssm-user` (the Session Manager login), `cloud-init status --wait` crashed with `PermissionError: [Errno 13] Permission denied: '/run/cloud-init/cloud.cfg'`. On this image that file is root-only. `sudo cloud-init status --wait` returned `status: done`.

**Lesson:** a Python traceback from a system tool is often just a permission problem. Read the last line first.

---

## 3 · A fresh terminal has no saved values

```
aws ssm start-session --target "$CLIENT_A"
Invalid length for parameter Target, value: 0, valid min length: 1
```

The new terminal was in my home folder and hadn't loaded `env.sh`, so `$CLIENT_A` was empty. I kept one terminal per client and opened each with a single chained line, so a session can never start without its values loaded:

```bash
cd ~/shared-storage && source ./env.sh && aws ssm start-session --target "$CLIENT_A"
```

When a session dropped after Session Manager's 20-minute idle timeout, the same line reconnected it.

---

## 4 · A new mount target isn't resolvable straight away

In the trap drill, my first `nfs-test` after creating the 1c mount target still failed with `Name or service not known` ([`18`](screenshots/18-step7-drill-dns-propagates-mounted.png)). The next attempt resolved `10.70.3.99` and mounted in 0.5 s. AWS documents up to 90 seconds before a new mount target's DNS record is available.

**Lesson:** after adding a mount target, a failed mount in the first minute or two isn't proof the fix is wrong. Wait, and retry until it resolves.

---

## 5 · Waiting on a silent loop

The wait loop for FSx for Windows prints nothing until it finishes, and after 20 minutes I couldn't tell "slow" from "stuck". A loop that only exits on `AVAILABLE` would wait forever on `FAILED`. I checked the real state from a second terminal:

```bash
aws fsx describe-file-systems --file-system-ids "$FSXW_ID" \
  --query 'FileSystems[0].{State:Lifecycle,Created:CreationTime,Why:FailureDetails.Message}' --output table
```

`CREATING`, no failure message: just slow. The file system was in use about 30 minutes after it was created.

**Lesson:** whenever I wait on AWS, I check the failure states too, not only the success state.

---

## 6 · Two security groups blocked each other's deletion

At teardown, the EFS and FSx for Windows groups deleted, but the Lustre and clients' groups both failed:

```
DependencyViolation ... resource sg-01bd… has a dependent object
DependencyViolation ... resource sg-02c6… has a dependent object
```

([`37`](screenshots/37-step14-sg-circular-reference-error.png)) The Lustre group allowed the clients' group in, and the clients' group allowed Lustre's callbacks. Each group was referenced by a rule in the other, so neither could go first. I revoked both groups' inbound rules, using each group's own rule list as the input, then both deleted and the VPC followed ([`38`](screenshots/38-step14-revoke-rules-then-delete.png)):

```bash
aws ec2 revoke-security-group-ingress --group-id "$CLIENT_SG" \
  --ip-permissions "$(aws ec2 describe-security-groups --group-ids "$CLIENT_SG" --query 'SecurityGroups[0].IpPermissions' --output json)"
```

**Lesson:** two-way security group references are normal for services like Lustre, but they turn teardown into a deadlock. The teardown now removes the rules first ([`teardown.md`](teardown.md)).

---

## 7 · Planned around before the build

- **Lustre client vs server version.** Amazon Linux 2023's Lustre 2.15 client refuses to connect to 2.10 file systems, and 2.10 is the default for Scratch. Creating the file system as **2.15** avoided a mount failure that would otherwise have appeared only after a 10-minute create.
- **Lustre security groups work both ways.** Per the FSx for Lustre documentation, the clients' group also needs inbound 988 and 1018–1023 from the file system's group.
- **AD names don't resolve from the VPC resolver.** Linux clients connected to the Windows share by its IP. A Route 53 Resolver rule forwarding `corp.kgotla.internal` to the domain controllers is the production fix.
- **Per-AZ availability.** Learning from an earlier build, where an instance class existed in the Region but not in my AZs, I checked both instance types per AZ before creating anything ([`01`](screenshots/01-step0-account-and-az-offerings.png)). Neither was offered in us-east-1e, and I wasn't using it.
- **`!` in queries.** Every clean-check query uses single quotes, so bash history expansion can't silently discard the check.

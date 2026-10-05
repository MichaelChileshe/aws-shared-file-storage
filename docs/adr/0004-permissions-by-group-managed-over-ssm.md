# ADR 0004: NTFS permissions by AD group, managed through APIs and SSM, not RDP

**Status:** Accepted
**Context:** Someone has to create users, put them in groups and set folder permissions. The usual way is to RDP into a Windows server with admin tools. That means an open port, a local password and actions nobody records.

## Decision

- **Users and groups** are created with the **Directory Service Data API** (`aws ds-data create-user`, `create-group`, `add-group-member`). Every change is an API call that CloudTrail records.
- **Passwords** are generated into Secrets Manager and set with `aws ds reset-user-password`, which also enables the account. They're never displayed.
- **Folder permissions** are set by a PowerShell script ([`set-finance-acl.ps1.tpl`](../../windows/set-finance-acl.ps1.tpl)) on a domain-joined admin server, sent through **SSM Run Command**. The server has no inbound rules and no key pair.
- Permissions go to the **Finance-Team group**, never to individual users. Grants are applied first, then inheritance is removed.

## Consequences

- The `\finance` ACL ended with exactly four entries, Finance-Team holding Modify, and SYSTEM keeping the Full Control FSx requires.
- Joining or leaving the finance team is a group change in AD, not a permission change on the folder.
- Run Command output is the record of what changed on the server and when.
- Interactive admin (browsing shares, ad-hoc fixes) still needs a session. Fleet Manager or Session Manager port forwarding provides it without opening RDP to a network.

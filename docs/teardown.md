# Teardown

The directory, FSx for Windows and Lustre bill by the hour, so teardown happened the same day. Nothing has deletion protection and there's no `Deny` statement anywhere, so every delete works for the account administrator.

The order matters where AWS enforces it:

- File systems and instances go first.
- The directory goes after the FSx file system joined to it.
- Security groups that reference each other need their rules removed first.

Run from the repo folder after `source ./env.sh`.

## A: start the slow deletions at once

```bash
aws fsx delete-file-system --file-system-id "$FSXW_ID" --windows-configuration SkipFinalBackup=true --query Lifecycle --output text
aws fsx delete-file-system --file-system-id "$LUSTRE_ID" --query Lifecycle --output text
aws ec2 terminate-instances --instance-ids "$CLIENT_A" "$CLIENT_B" "$CLIENT_C" "$WIN_ID" --query 'TerminatingInstances[].CurrentState.Name' --output text
aws efs delete-access-point --access-point-id "$EFS_AP"
for mt in $(aws efs describe-mount-targets --file-system-id "$EFS_ID" --query 'MountTargets[].MountTargetId' --output text); do aws efs delete-mount-target --mount-target-id "$mt"; done
```

## B: EFS, then the directory once FSx is gone

```bash
until [ "$(aws efs describe-mount-targets --file-system-id "$EFS_ID" --query 'length(MountTargets)' --output text)" = "0" ]; do sleep 15; done
aws efs delete-file-system --file-system-id "$EFS_ID"
aws ec2 wait instance-terminated --instance-ids "$CLIENT_A" "$CLIENT_B" "$CLIENT_C" "$WIN_ID"
until [ "$(aws fsx describe-file-systems --query 'length(FileSystems)' --output text)" = "0" ]; do sleep 30; done
aws ds delete-directory --directory-id "$AD_ID" --query DirectoryId --output text
```

## C: bucket and secrets

```bash
aws s3 rm "s3://$BUCKET" --recursive --only-show-errors
aws s3api delete-bucket --bucket "$BUCKET"
for s in kgotla/ad-admin kgotla/ad-thabo kgotla/ad-lerato; do aws secretsmanager delete-secret --secret-id "$s" --force-delete-without-recovery --query Name --output text; done
```

## D: IAM, once the directory has gone

```bash
until [ "$(aws ds describe-directories --query 'length(DirectoryDescriptions[?DirectoryId==`'"$AD_ID"'`])' --output text)" = "0" ]; do sleep 30; done
for r in client admin; do aws iam remove-role-from-instance-profile --instance-profile-name storage-$r-profile --role-name storage-$r-role; aws iam delete-instance-profile --instance-profile-name storage-$r-profile; aws iam detach-role-policy --role-name storage-$r-role --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore; aws iam delete-role-policy --role-name storage-$r-role --policy-name storage-$r; done
aws iam detach-role-policy --role-name storage-admin-role --policy-arn arn:aws:iam::aws:policy/AmazonSSMDirectoryServiceAccess
aws iam delete-role --role-name storage-client-role
aws iam delete-role --role-name storage-admin-role
```

## E: network, with the security group references removed first

The Lustre group and the clients' group reference each other, so neither can be deleted while the other's rules exist ([debugging note 6](debugging-journey.md)). Remove every inbound rule from both, then delete:

```bash
for g in "$CLIENT_SG" "$LUSTRE_SG"; do aws ec2 revoke-security-group-ingress --group-id "$g" --ip-permissions "$(aws ec2 describe-security-groups --group-ids "$g" --query 'SecurityGroups[0].IpPermissions' --output json)" --query Return --output text; done
for g in "$EFS_SG" "$FSXW_SG" "$LUSTRE_SG" "$CLIENT_SG"; do aws ec2 delete-security-group --group-id "$g" --query Return --output text; done
for s in "$SUB_A" "$SUB_B" "$SUB_C"; do aws ec2 delete-subnet --subnet-id "$s"; done
aws ec2 delete-route-table --route-table-id "$RT_ID"
aws ec2 detach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID"
aws ec2 delete-internet-gateway --internet-gateway-id "$IGW_ID"
aws ec2 delete-vpc --vpc-id "$VPC_ID"
```

The directory's own security group is deleted by AWS with the directory. A `DependencyViolation` on a subnet means a network interface from EFS, FSx or the directory is still being released: wait a minute and run that line again.

## Clean check

Every query uses single quotes, so bash can't history-expand anything inside it:

```bash
aws efs describe-file-systems --query 'FileSystems[?Name==`urg-design-files`].FileSystemId' --output text
aws fsx describe-file-systems --query 'FileSystems[].FileSystemId' --output text
aws ds describe-directories --query 'DirectoryDescriptions[].DirectoryId' --output text
aws ec2 describe-instances --filters Name=tag:Name,Values=storage-client-a,storage-client-b,storage-client-c,kgotla-admin Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId' --output text
aws ec2 describe-vpcs --filters Name=tag:Name,Values=storage-lab-vpc --query 'Vpcs[].VpcId' --output text
aws s3api list-buckets --query 'Buckets[?starts_with(Name,`themba-actuarial`)].Name' --output text
aws secretsmanager list-secrets --query 'SecretList[?starts_with(Name,`kgotla/`)].Name' --output text
aws iam list-roles --query 'Roles[?starts_with(RoleName,`storage-`)].RoleName' --output text
```

My result: every line empty ([`39`](screenshots/39-step14-clean-check.png)).

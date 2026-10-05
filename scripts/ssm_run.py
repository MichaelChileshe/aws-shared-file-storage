#!/usr/bin/env python3
"""Run something on the Windows admin server through SSM Run Command, wait for it, and print the output.
No RDP, no open port: the instance's SSM agent pulls the command.

  python3 scripts/ssm_run.py join <instance-id>                     join the instance to the AD domain
  python3 scripts/ssm_run.py ps <instance-id> <script.ps1>          run a PowerShell script file
  python3 scripts/ssm_run.py cmd <instance-id> "<PowerShell line>"  run one PowerShell line
"""
import json, sys, time
from kit_aws import aws, env


def wait_online(iid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        info = aws("ssm", "describe-instance-information",
                   "--filters", f"Key=InstanceIds,Values={iid}")["InstanceInformationList"]
        if info and info[0]["PingStatus"] == "Online":
            print(f"{iid} is Online in Systems Manager ({info[0].get('PlatformName', '')})")
            return
        print(f"  waiting for {iid} to register with Systems Manager ...", flush=True)
        time.sleep(20)
    sys.exit(f"{iid} did not come Online in SSM within {timeout // 60} minutes")


def send(iid, document, params, comment):
    cid = aws("ssm", "send-command", "--instance-ids", iid, "--document-name", document,
              "--comment", comment, "--parameters", json.dumps(params))["Command"]["CommandId"]
    print(f"command {cid} sent ({document})", flush=True)
    t0 = time.time()
    while True:
        time.sleep(5)
        res = aws_quiet("ssm", "get-command-invocation", "--command-id", cid, "--instance-id", iid)
        if not res:
            continue
        status = res["Status"]
        if status in ("Pending", "InProgress", "Delayed"):
            if int(time.time() - t0) % 30 < 5:
                print(f"  {status} ({int(time.time() - t0)} s)", flush=True)
            continue
        print(f"\nSTATUS: {status}  ({int(time.time() - t0)} s)")
        if res.get("StandardOutputContent", "").strip():
            print("----- output -----\n" + res["StandardOutputContent"].rstrip())
        if res.get("StandardErrorContent", "").strip():
            print("----- errors -----\n" + res["StandardErrorContent"].rstrip())
        if status != "Success":
            sys.exit(1)
        return


def aws_quiet(*args):
    """get-command-invocation can briefly return InvocationDoesNotExist right after send-command."""
    import subprocess
    r = subprocess.run(["aws", *args, "--output", "json"], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    action, iid = sys.argv[1], sys.argv[2]
    wait_online(iid)
    if action == "join":
        ad_id, domain = env("AD_ID"), env("AD_DOMAIN")
        dns = aws("ds", "describe-directories", "--directory-ids", ad_id)["DirectoryDescriptions"][0]["DnsIpAddrs"]
        send(iid, "AWS-JoinDirectoryServiceDomain",
             {"directoryId": [ad_id], "directoryName": [domain], "dnsIpAddresses": dns},
             "join the AD domain")
    elif action == "ps":
        lines = open(sys.argv[3]).read().splitlines()
        send(iid, "AWS-RunPowerShellScript", {"commands": lines}, f"run {sys.argv[3]}")
    elif action == "cmd":
        send(iid, "AWS-RunPowerShellScript", {"commands": [sys.argv[3]]}, "one command")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

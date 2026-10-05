#!/usr/bin/env python3
"""fstool - mounts and measures the three shared file systems from a Linux client. Runs as root (via sudo).

It finds every file system by its Name tag through the AWS CLI and the instance role, so no IDs,
IP addresses or passwords are ever typed.

  fstool mount efs                      EFS through the design team's access point, TLS   -> /mnt/efs
  fstool mount lustre                   FSx for Lustre scratch file system                -> /mnt/lustre
  fstool mount smb <user>               FSx for Windows share as an AD user, SMB 3 + seal  -> /mnt/smb-<user>
  fstool mount smb <user> --bad-password   the same with a wrong password (expect error 13)
  fstool bench <directory> <label>      fio sequential write/read (4 x 256 MiB) + 1,000 small files
  fstool results                        every bench result so far, as a table
  fstool dataset                        build the actuarial dataset (32 x 32 MiB CSV) and upload it to S3
  fstool hydrate                        first read (lazy-loaded from S3) vs second read (from Lustre)
  fstool nfs-test                       plain NFS mount of EFS by its DNS name (25 s limit), then unmount

Python 3.9 compatible (Amazon Linux 2023).
"""
import csv
import json
import os
import random
import secrets
import subprocess
import sys
import time

CONFIG = json.load(open(os.environ.get("FSTOOL_CONFIG", "/opt/fstool/config.json")))
REGION = CONFIG["region"]
BUCKET = CONFIG["bucket"]
RESULTS = "/opt/fstool/results.csv"

EFS_NAME = "urg-design-files"
EFS_AP_NAME = "urg-design-ap"
LUSTRE_NAME = "themba-actuarial-scratch"
FSXW_NAME = "kgotla-backoffice"
AD_SHORT = "KGOTLA"
DATASET_PREFIX = "actuarial"
DATASET_FILES, DATASET_MIB = 32, 32


def out(msg=""):
    print(msg, flush=True)


def die(msg):
    sys.exit(f"\nERROR: {msg}\n")


def aws(*args):
    res = subprocess.run(["aws", *args, "--region", REGION, "--output", "json"], capture_output=True, text=True)
    if res.returncode != 0:
        die(f"aws {' '.join(args[:2])} failed:\n{res.stderr.strip()}")
    return json.loads(res.stdout) if res.stdout.strip() else {}


def run(cmd, check=True):
    """Run a shell command, print it, return (exit code, combined output)."""
    out(f"$ {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    text = (res.stdout + res.stderr).strip()
    if text:
        out(text)
    if check and res.returncode != 0:
        die(f"command failed (exit {res.returncode})")
    return res.returncode, text


def tag(tags, key="Name"):
    for t in tags or []:
        if t.get("Key") == key:
            return t.get("Value")
    return None


def drop_caches():
    subprocess.run("sync; echo 3 > /proc/sys/vm/drop_caches", shell=True, check=True)


def is_mounted(path):
    return subprocess.run(["mountpoint", "-q", path]).returncode == 0


# ---------------------------------------------------------------- discovery
def efs_ids():
    fss = [f for f in aws("efs", "describe-file-systems")["FileSystems"] if f.get("Name") == EFS_NAME]
    if not fss:
        die(f"no EFS file system named {EFS_NAME}")
    fs_id = fss[0]["FileSystemId"]
    aps = aws("efs", "describe-access-points", "--file-system-id", fs_id)["AccessPoints"]
    ap = [a for a in aps if a.get("Name") == EFS_AP_NAME or tag(a.get("Tags")) == EFS_AP_NAME]
    if not ap:
        die(f"no access point named {EFS_AP_NAME} on {fs_id}")
    return fs_id, ap[0]["AccessPointId"]


def fsx(name, fs_type):
    for f in aws("fsx", "describe-file-systems")["FileSystems"]:
        if f["FileSystemType"] == fs_type and tag(f.get("Tags")) == name:
            if f["Lifecycle"] != "AVAILABLE":
                die(f"{name} is {f['Lifecycle']}, not AVAILABLE yet")
            return f
    die(f"no {fs_type} file system named {name}")


# ---------------------------------------------------------------- mount
def mount(args):
    if not args:
        die("usage: fstool mount efs | lustre | smb <user> [--bad-password]")
    kind = args[0]
    if kind == "efs":
        fs_id, ap_id = efs_ids()
        target = "/mnt/efs"
        if is_mounted(target):
            out(f"{target} is already mounted")
            return
        os.makedirs(target, exist_ok=True)
        run(f"mount -t efs -o tls,accesspoint={ap_id} {fs_id}:/ {target}")
        out(f"mounted EFS {fs_id} through access point {ap_id} (TLS) at {target}")
    elif kind == "lustre":
        f = fsx(LUSTRE_NAME, "LUSTRE")
        target = "/mnt/lustre"
        if is_mounted(target):
            out(f"{target} is already mounted")
            return
        os.makedirs(target, exist_ok=True)
        mount_name = f["LustreConfiguration"]["MountName"]
        run(f"mount -t lustre -o relatime,flock {f['DNSName']}@tcp:/{mount_name} {target}")
        out(f"mounted FSx for Lustre {f['FileSystemId']} at {target}")
    elif kind == "smb":
        if len(args) < 2:
            die("usage: fstool mount smb <user> [--bad-password]")
        user, bad = args[1], "--bad-password" in args
        f = fsx(FSXW_NAME, "WINDOWS")
        ip = f["WindowsConfiguration"]["PreferredFileServerIp"]
        if bad:
            password = secrets.token_urlsafe(16)
            target, cred = "/mnt/smb-bad", "/root/.smb-bad"
        else:
            password = aws("secretsmanager", "get-secret-value", "--secret-id", f"kgotla/ad-{user}")["SecretString"]
            target, cred = f"/mnt/smb-{user}", f"/root/.smb-{user}"
        if is_mounted(target):
            out(f"{target} is already mounted")
            return
        os.makedirs(target, exist_ok=True)
        fd = os.open(cred, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(f"username={user}\npassword={password}\ndomain={AD_SHORT}\n")
        code, _ = run(f"mount -t cifs //{ip}/share {target} -o credentials={cred},vers=3.1.1,seal,uid=0,gid=0",
                      check=False)
        os.remove(cred)
        if code == 0:
            out(f"mounted \\\\{ip}\\share as {AD_SHORT}\\{user} (SMB 3.1.1, encrypted) at {target}")
        else:
            out(f"mount as {AD_SHORT}\\{user} REFUSED (exit {code})")
    else:
        die(f"unknown file system '{kind}'")


# ---------------------------------------------------------------- bench
def fio(directory, rw):
    cmd = ["fio", "--name=seq", f"--directory={directory}", f"--rw={rw}", "--bs=1M", "--size=256M",
           "--numjobs=4", "--ioengine=psync", "--group_reporting", "--output-format=json"]
    if rw == "write":
        cmd.append("--end_fsync=1")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        die(f"fio {rw} failed in {directory}:\n{res.stderr.strip()[-800:]}")
    job = json.loads(res.stdout[res.stdout.find("{"):])["jobs"][0]
    return job[rw]["bw_bytes"] / 1e6


def small_files(directory, n=1000):
    d = os.path.join(directory, "small")
    os.makedirs(d, exist_ok=True)
    payload = os.urandom(4096)
    t0 = time.monotonic()
    for i in range(n):
        with open(os.path.join(d, f"f{i:05d}.dat"), "wb") as fh:
            fh.write(payload)
    os.sync()
    create = n / (time.monotonic() - t0)
    drop_caches()
    t0 = time.monotonic()
    for i in range(n):
        with open(os.path.join(d, f"f{i:05d}.dat"), "rb") as fh:
            fh.read()
    read = n / (time.monotonic() - t0)
    subprocess.run(["rm", "-rf", d])
    return create, read


def bench(args):
    if len(args) != 2:
        die("usage: fstool bench <directory> <label>")
    directory, label = args
    os.makedirs(directory, exist_ok=True)
    out(f"{time.strftime('%H:%M:%S')}  bench '{label}' in {directory}: fio 4 x 256 MiB write, read, then 1,000 x 4 KiB files")
    w = fio(directory, "write")
    out(f"  sequential write : {w:8.1f} MB/s")
    drop_caches()
    r = fio(directory, "read")
    out(f"  sequential read  : {r:8.1f} MB/s   (page cache dropped first)")
    subprocess.run(f"rm -f {directory}/seq.*", shell=True)
    c, rd = small_files(directory)
    out(f"  small files      : {c:8.0f} created/s   {rd:8.0f} read/s")
    new = not os.path.exists(RESULTS)
    with open(RESULTS, "a", newline="") as fh:
        wr = csv.writer(fh)
        if new:
            wr.writerow(["time", "label", "directory", "write_MBps", "read_MBps", "small_create_per_s", "small_read_per_s"])
        wr.writerow([time.strftime("%H:%M:%S"), label, directory, f"{w:.1f}", f"{r:.1f}", f"{c:.0f}", f"{rd:.0f}"])
    out(f"  saved to {RESULTS}")


def results(_args):
    if not os.path.exists(RESULTS):
        die("no results yet")
    rows = list(csv.DictReader(open(RESULTS)))
    out(f"{'label':<14}{'write MB/s':>12}{'read MB/s':>12}{'small create/s':>16}{'small read/s':>14}")
    for r in rows:
        out(f"{r['label']:<14}{r['write_MBps']:>12}{r['read_MBps']:>12}{r['small_create_per_s']:>16}{r['small_read_per_s']:>14}")


# ---------------------------------------------------------------- dataset + hydration
def dataset(_args):
    local = "/var/tmp/actuarial"
    os.makedirs(local, exist_ok=True)
    rnd = random.Random(42)
    products = ["FUNERAL", "LIFE", "MOTOR", "HOUSEHOLD", "DISABILITY"]
    target = DATASET_MIB * 1024 * 1024
    out(f"building {DATASET_FILES} x {DATASET_MIB} MiB policy-experience files in {local}")
    for i in range(DATASET_FILES):
        path = os.path.join(local, f"experience-{i:02d}.csv")
        with open(path, "w") as fh:
            fh.write("policy_id,product,age,sum_assured_zar,annual_premium_zar,claims_count,claims_zar\n")
            size, n = 0, 0
            while size < target:
                n += 1
                line = (f"P{i:02d}{n:08d},{rnd.choice(products)},{rnd.randint(18, 75)},"
                        f"{rnd.randint(20, 3000) * 1000},{rnd.randint(600, 60000)},"
                        f"{rnd.choice([0, 0, 0, 1, 1, 2])},{rnd.randint(0, 250000)}\n")
                fh.write(line)
                size += len(line)
    run(f"aws s3 cp {local} s3://{BUCKET}/{DATASET_PREFIX}/ --recursive --only-show-errors --region {REGION}")
    run(f"aws s3 ls s3://{BUCKET}/{DATASET_PREFIX}/ --summarize --human-readable --region {REGION} | tail -2")
    subprocess.run(["rm", "-rf", local])


def read_all(files):
    total = 0
    t0 = time.monotonic()
    for p in files:
        with open(p, "rb") as fh:
            while True:
                chunk = fh.read(4 * 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
    return total, time.monotonic() - t0


def hydrate(_args):
    root = "/mnt/lustre"
    if not is_mounted(root):
        die("mount Lustre first: fstool mount lustre")
    files = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs if f.endswith(".csv"))
    if not files:
        die("no .csv files under /mnt/lustre (was the file system created with the S3 import path?)")
    out(f"{len(files)} files visible under {root} (metadata imported from s3://{BUCKET}/{DATASET_PREFIX}/)")
    run(f"lfs hsm_state {files[0]}", check=False)
    drop_caches()
    b1, t1 = read_all(files)
    out(f"first read  : {b1 / 1e6:8.1f} MB in {t1:6.1f} s = {b1 / 1e6 / t1:7.1f} MB/s   (lazy-loaded from S3)")
    run(f"lfs hsm_state {files[0]}", check=False)
    drop_caches()
    b2, t2 = read_all(files)
    out(f"second read : {b2 / 1e6:8.1f} MB in {t2:6.1f} s = {b2 / 1e6 / t2:7.1f} MB/s   (served by Lustre)")
    out(f"speed-up    : {t1 / t2:.1f}x")


# ---------------------------------------------------------------- the EFS trap drill
def nfs_test(_args):
    fs_id, _ = efs_ids()
    dns = f"{fs_id}.efs.{REGION}.amazonaws.com"
    target = "/mnt/efs-plain"
    os.makedirs(target, exist_ok=True)
    if is_mounted(target):
        subprocess.run(["umount", target])
    code, _ = run(f"getent hosts {dns}", check=False)
    if code != 0:
        out("-> DNS: the name does not resolve from this Availability Zone")
    t0 = time.monotonic()
    code, _ = run(f"timeout -k 5 25 mount -t nfs -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,"
                  f"noresvport {dns}:/ {target}", check=False)
    took = time.monotonic() - t0
    if code == 0:
        out(f"RESULT: MOUNTED in {took:.1f} s")
        run(f"ls -ln {target}", check=False)
        subprocess.run(["umount", target])
    elif code in (124, 137):
        out(f"RESULT: TIMED OUT after {took:.0f} s (nothing answered on TCP 2049)")
    else:
        out(f"RESULT: FAILED after {took:.1f} s (exit {code})")


def main():
    if os.geteuid() != 0:
        die("run as root (the fstool wrapper uses sudo)")
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        out(__doc__)
        return
    cmds = {"mount": mount, "bench": bench, "results": results, "dataset": dataset, "hydrate": hydrate,
            "nfs-test": nfs_test}
    if sys.argv[1] not in cmds:
        die(f"unknown command '{sys.argv[1]}'")
    cmds[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()

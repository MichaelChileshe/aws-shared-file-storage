#!/usr/bin/env python3
"""Build the clients' boot script: the template with the region and bucket filled in and the fstool tool
embedded (gzip-compressed + base64, so it stays well inside EC2's 16 KB user-data limit).

Usage:  python3 scripts/build_userdata.py            -> writes build/userdata.sh
"""
import base64, gzip, os, textwrap
from kit_aws import ROOT, env

tpl = open(os.path.join(ROOT, "client", "userdata.sh.tpl")).read()
tool = open(os.path.join(ROOT, "client", "fstool.py"), "rb").read()
packed = base64.b64encode(gzip.compress(tool, 9)).decode()
packed = "\n".join(textwrap.wrap(packed, 76))
text = (tpl.replace("@@REGION@@", env("REGION"))
           .replace("@@BUCKET@@", env("BUCKET"))
           .replace("@@FSTOOL_GZ_B64@@", packed))
os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
dst = os.path.join(ROOT, "build", "userdata.sh")
with open(dst, "w", newline="\n") as f:
    f.write(text)
size = os.path.getsize(dst)
print(f"built {dst}  ({size:,} bytes; EC2 limit is 16,384)")
if size > 16384:
    raise SystemExit("too big for EC2 user data")

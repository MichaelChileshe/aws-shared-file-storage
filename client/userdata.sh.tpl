#!/bin/bash
# Boot script for the storage test clients: NFS/EFS, SMB and Lustre clients, fio, and the fstool tool.
set -euxo pipefail

dnf install -y amazon-efs-utils cifs-utils fio lustre-client

mkdir -p /opt/fstool
cat > /opt/fstool/config.json <<'CFG'
{"region": "@@REGION@@", "bucket": "@@BUCKET@@"}
CFG

# the fstool tool, gzip-compressed and base64-encoded
base64 -d <<'FSTOOL' | gunzip > /opt/fstool/fstool.py
@@FSTOOL_GZ_B64@@
FSTOOL

printf '#!/bin/bash\nexec sudo python3 /opt/fstool/fstool.py "$@"\n' > /usr/local/bin/fstool
chmod 755 /usr/local/bin/fstool /opt/fstool/fstool.py
rpm -q amazon-efs-utils cifs-utils fio lustre-client
echo "fstool ready"

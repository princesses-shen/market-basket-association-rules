#!/usr/bin/env bash
# Prepare an existing Ubuntu VMware guest for local development.
set -euo pipefail

TARGET_USER="${SUDO_USER:-hadoop}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

apt-get -o DPkg::Lock::Timeout=600 update
DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 install -y maven python3-pip python3-venv openssh-client

cat >/etc/profile.d/recruit-bigdata.sh <<'EOF'
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=/opt/hadoop
export HBASE_HOME=/opt/hbase
export PATH="$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$HBASE_HOME/bin"
EOF

# Hadoop's start scripts SSH back into the single-node guest.
install -d -m 700 -o "$TARGET_USER" -g "$TARGET_USER" "$TARGET_HOME/.ssh"
if [[ ! -f "$TARGET_HOME/.ssh/id_ed25519" ]]; then
  sudo -u "$TARGET_USER" ssh-keygen -q -t ed25519 -N '' -f "$TARGET_HOME/.ssh/id_ed25519"
fi
touch "$TARGET_HOME/.ssh/authorized_keys"
cat "$TARGET_HOME/.ssh/id_ed25519.pub" >>"$TARGET_HOME/.ssh/authorized_keys"
sort -u "$TARGET_HOME/.ssh/authorized_keys" -o "$TARGET_HOME/.ssh/authorized_keys"
chown "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.ssh/authorized_keys"
chmod 600 "$TARGET_HOME/.ssh/authorized_keys"
sudo -u "$TARGET_USER" ssh-keyscan -H localhost 127.0.0.1 "$(hostname)" >>"$TARGET_HOME/.ssh/known_hosts" 2>/dev/null || true
chown "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.ssh/known_hosts"
chmod 600 "$TARGET_HOME/.ssh/known_hosts"

mkdir -p "$TARGET_HOME/day08" "$TARGET_HOME/predict" "$TARGET_HOME/recruit-project"
chown -R "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/day08" "$TARGET_HOME/predict" "$TARGET_HOME/recruit-project"

echo "VM preparation complete for $TARGET_USER"

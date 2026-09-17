# -*- coding: utf-8 -*-
"""Deploy the project to the VMware guest configured in config/local.env.

Usage:
    python scripts/deploy_local_vm.py check
    python scripts/deploy_local_vm.py all

The script never stores credentials in tracked files.  It reads the ignored
config/local.env and deploys to /home/<VM_SSH_USER>.
"""

import argparse
import os
import posixpath
import stat
import sys
import time

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config  # noqa: E402


class VM:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        self.client.connect(
            config.VM_HOST,
            username=config.VM_SSH_USER,
            password=config.VM_SSH_PASSWORD,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )

    def close(self):
        self.client.close()

    def run(self, command, timeout=900, sudo=False, check=True):
        if sudo:
            command = "sudo -S -p '' bash -lc " + shell_quote(command)
        print("\n$ " + command[:180] + ("..." if len(command) > 180 else ""))
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout, get_pty=False)
        if sudo:
            stdin.write(config.VM_SSH_PASSWORD + "\n")
            stdin.flush()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        if out.strip(): print(out)
        if err.strip(): print(err, file=sys.stderr)
        if check and code != 0:
            raise RuntimeError("remote command failed with exit code %s" % code)
        return code, out, err

    def mkdir(self, sftp, remote_dir):
        parts = []
        current = remote_dir
        while current not in ("", "/"):
            parts.append(current)
            current = posixpath.dirname(current)
        for directory in reversed(parts):
            try:
                sftp.stat(directory)
            except IOError:
                sftp.mkdir(directory)

    def upload_file(self, local_path, remote_path):
        sftp = self.client.open_sftp()
        try:
            self.mkdir(sftp, posixpath.dirname(remote_path))
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()

    def upload_tree(self, local_dir, remote_dir):
        excluded_dirs = {".git", "target", "__pycache__", ".idea", ".vscode"}
        excluded_files = {"local.env", "start_website.log"}
        sftp = self.client.open_sftp()
        uploaded = 0
        try:
            self.mkdir(sftp, remote_dir)
            for base, dirs, files in os.walk(local_dir):
                dirs[:] = [d for d in dirs if d not in excluded_dirs]
                relative = os.path.relpath(base, local_dir)
                target_dir = remote_dir if relative == "." else posixpath.join(remote_dir, relative.replace("\\", "/"))
                self.mkdir(sftp, target_dir)
                for name in files:
                    if name in excluded_files or name.endswith((".pyc", ".log")):
                        continue
                    sftp.put(os.path.join(base, name), posixpath.join(target_dir, name))
                    uploaded += 1
        finally:
            sftp.close()
        print("Uploaded %d files to %s" % (uploaded, remote_dir))


def shell_quote(value):
    return "'" + value.replace("'", "'\\''") + "'"


def env_prefix():
    return (
        "export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64; "
        "export HADOOP_HOME=/opt/hadoop; export HBASE_HOME=/opt/hbase; "
        "export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$HBASE_HOME/bin; "
    )


def prepare(vm):
    local = os.path.join(ROOT, "deploy", "setup", "prepare_local_vm.sh")
    remote = "/tmp/prepare_local_vm.sh"
    vm.upload_file(local, remote)
    vm.run("chmod +x %s && %s" % (remote, remote), sudo=True, timeout=1200)


def start_data(vm):
    prefix = env_prefix()
    vm.run("ssh -o BatchMode=yes -o ConnectTimeout=5 localhost true")
    vm.run(prefix + "jps | grep -q NameNode || $HADOOP_HOME/sbin/start-dfs.sh", timeout=180)
    vm.run(prefix + "jps | grep -q ResourceManager || $HADOOP_HOME/sbin/start-yarn.sh", timeout=180, check=False)
    time.sleep(5)
    vm.run(prefix + "jps | grep -q HMaster || $HBASE_HOME/bin/start-hbase.sh", timeout=180)
    time.sleep(8)
    vm.run(prefix + "jps | grep -q ThriftServer || $HBASE_HOME/bin/hbase-daemon.sh start thrift", timeout=120, check=False)
    time.sleep(5)
    vm.run(prefix + "jps; ss -lnt", timeout=30)


def upload_sources(vm):
    remote_home = "/home/" + config.VM_SSH_USER
    vm.upload_tree(os.path.join(ROOT, "day08-backend"), remote_home + "/day08")

    # Files used to seed HBase.
    for relative in ("config.py", "scripts/gen_data.py"):
        vm.upload_file(os.path.join(ROOT, *relative.split("/")), remote_home + "/recruit-project/" + relative)
    remote_env = (
        "VM_HOST=127.0.0.1\nVM_SSH_USER=%s\nVM_SSH_PASSWORD=\n"
        "HBASE_HOST=127.0.0.1\nHBASE_PORT=9090\n" % config.VM_SSH_USER
    )
    sftp = vm.client.open_sftp()
    try:
        vm.mkdir(sftp, remote_home + "/recruit-project/config")
        with sftp.file(remote_home + "/recruit-project/config/local.env", "w") as handle:
            handle.write(remote_env)
    finally:
        sftp.close()

    # Prediction service layout expected by serve_api.py.
    vm.upload_file(
        os.path.join(ROOT, "src", "serving", "predict_api", "serve_api.py"),
        remote_home + "/predict/serve_api.py",
    )
    vm.upload_file(
        os.path.join(ROOT, "src", "analysis", "features.py"),
        remote_home + "/predict/src/analysis/features.py",
    )
    vm.upload_file(
        os.path.join(ROOT, "artifacts", "models", "salary_predictor.pkl"),
        remote_home + "/predict/artifacts/models/salary_predictor.pkl",
    )


def seed_data(vm):
    remote_home = "/home/" + config.VM_SSH_USER
    command = (
        "python3 -m venv %(home)s/recruit-venv; "
        "%(home)s/recruit-venv/bin/pip install -q happybase thriftpy2; "
        "cd %(home)s/recruit-project; %(home)s/recruit-venv/bin/python scripts/gen_data.py"
    ) % {"home": remote_home}
    vm.run(command, timeout=1200)


def build_backend(vm):
    remote_home = "/home/" + config.VM_SSH_USER
    vm.run(
        env_prefix() + "cd %s/day08 && mvn clean package -DskipTests" % remote_home,
        timeout=1800,
    )
    vm.run(
        "test ! -f %(home)s/day08/app.pid || kill $(cat %(home)s/day08/app.pid) 2>/dev/null || true"
        % {"home": remote_home},
        timeout=30,
        check=False,
    )
    vm.run(
        env_prefix()
        + "cd %(home)s/day08; nohup java -jar target/demo-0.0.1-SNAPSHOT.jar "
          "--hbase.zookeeper.quorum=127.0.0.1 > app.log 2>&1 < /dev/null & echo $! > app.pid"
        % {"home": remote_home},
        timeout=30,
    )
    time.sleep(18)
    vm.run("tail -40 %s/day08/app.log" % remote_home, timeout=30)


def start_predict(vm):
    remote_home = "/home/" + config.VM_SSH_USER
    command = (
        "python3 -m venv %(home)s/predict/.venv; "
        "%(home)s/predict/.venv/bin/python -c 'import numpy, sklearn, xgboost' 2>/dev/null || "
        "%(home)s/predict/.venv/bin/pip install -q -i https://pypi.tuna.tsinghua.edu.cn/simple "
        "--timeout 60 numpy scikit-learn xgboost; "
        "test ! -f %(home)s/predict/predict.pid || "
        "kill $(cat %(home)s/predict/predict.pid) 2>/dev/null || true; "
        "cd %(home)s/predict; nohup .venv/bin/python serve_api.py 8788 "
        "> predict.log 2>&1 < /dev/null & echo $! > predict.pid"
    ) % {"home": remote_home}
    vm.run(command, timeout=1800)
    time.sleep(8)
    vm.run("tail -30 %s/predict/predict.log" % remote_home, timeout=30, check=False)


def start_runtime(vm):
    """Start an already deployed copy without rebuilding or reseeding it."""
    remote_home = "/home/" + config.VM_SSH_USER
    start_data(vm)
    backend = (
        env_prefix()
        + "if ! ss -lnt | grep -q ':8080 '; then cd %(home)s/day08; "
          "nohup java -jar target/demo-0.0.1-SNAPSHOT.jar "
          "--hbase.zookeeper.quorum=127.0.0.1 > app.log 2>&1 < /dev/null & "
          "echo $! > app.pid; fi"
        % {"home": remote_home}
    )
    vm.run(backend, timeout=30)
    predict = (
        "if ! ss -lnt | grep -q ':8788 '; then cd %(home)s/predict; "
        "nohup .venv/bin/python serve_api.py 8788 > predict.log 2>&1 < /dev/null & "
        "echo $! > predict.pid; fi"
        % {"home": remote_home}
    )
    vm.run(predict, timeout=30, check=False)
    time.sleep(12)


def check(vm):
    vm.run(env_prefix() + "hostname; whoami; java -version; mvn -version; jps; ss -lnt", timeout=60, check=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "prepare", "start", "start-data", "upload", "seed", "build", "predict", "all"))
    args = parser.parse_args()
    vm = VM()
    vm.connect()
    try:
        if args.action in ("prepare", "all"): prepare(vm)
        if args.action == "start": start_runtime(vm)
        if args.action in ("start-data", "all"): start_data(vm)
        if args.action in ("upload", "all"): upload_sources(vm)
        if args.action in ("seed", "all"): seed_data(vm)
        if args.action in ("build", "all"): build_backend(vm)
        if args.action in ("predict", "all"): start_predict(vm)
        check(vm)
    finally:
        vm.close()


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""部署招聘网站到虚拟机：SFTP 上传 Java + 前端 + mvn 打包 + 启动。"""
import paramiko
import os
import sys
import time
import shlex

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

HOST = config.VM_HOST
USER = config.VM_SSH_USER
PASS = config.VM_SSH_PASSWORD
REMOTE_ROOT = os.environ.get("VM_REMOTE_ROOT", "/home/" + USER + "/day08")
LOCAL_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "day08-backend")

def ssh():
    c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    return c

def run(c, cmd, timeout=600):
    print(f"\n$ {cmd[:90]}{'...' if len(cmd)>90 else ''}")
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if out: print(out)
    if err.strip() and "Warning" not in err: print("[err]", err[:500])
    if o.channel.recv_exit_status() != 0:
        raise RuntimeError("Remote command failed; deployment stopped.")
    return out

def fire(c, cmd):
    transport = c.get_transport(); ch = transport.open_session()
    ch.exec_command("setsid bash -c '" + cmd.replace("'", "'\\''") + "' &\nexit 0\n")
    time.sleep(3)
    try: ch.close()
    except: pass

def upload_dir(sftp, local_dir, remote_dir, skip_echarts=True):
    """递归上传目录"""
    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = remote_dir + "/" + item
        if os.path.isdir(local_path):
            # 建远程目录
            try: sftp.stat(remote_path)
            except: sftp.mkdir(remote_path)
            upload_dir(sftp, local_path, remote_path, skip_echarts)
        else:
            if skip_echarts and ("echarts" in item):
                print(f"  跳过 {item}（VM 已有）")
                continue
            print(f"  上传 {remote_path}")
            sftp.put(local_path, remote_path)

def main():
    print(">>> 1. 连接虚拟机")
    c = ssh(); sftp = c.open_sftp()
    
    # Upload the entire source tree, including security classes and nested pages.
    run(c, "mkdir -p " + shlex.quote(REMOTE_ROOT + "/src") + " " + shlex.quote(REMOTE_ROOT + "/deploy/run"))
    upload_dir(sftp, os.path.join(LOCAL_ROOT, "src"), REMOTE_ROOT + "/src", skip_echarts=False)
    sftp.put(os.path.join(LOCAL_ROOT, "pom.xml"), REMOTE_ROOT + "/pom.xml")
    run_local = os.path.join(LOCAL_ROOT, "..", "deploy", "run")
    for name in ("account_env.sh", "s5_backend_start.sh", "vm_autostart.sh"):
        sftp.put(os.path.join(run_local, name), REMOTE_ROOT + "/deploy/run/" + name)
    # Private SMTP configuration is managed separately on the target; never upload it with source.
    sftp.close()
    
    # Build and test before stopping the existing application.
    remote = shlex.quote(REMOTE_ROOT)
    run(c, f"cd {remote} && export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 && "
           "export PATH=$JAVA_HOME/bin:$PATH && mvn package -B", timeout=600)
    run(c, "pkill -f '[d]emo-0.0.1-SNAPSHOT.jar' 2>/dev/null || true", timeout=15)
    fire(c, f"cd {remote} && export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 && "
            "export PATH=$JAVA_HOME/bin:$PATH && "
            f"export ACCOUNT_SECURITY_ENV={shlex.quote(REMOTE_ROOT + '/config/account-security.env')} && "
            ". ./deploy/run/account_env.sh && "
            "nohup java -jar target/demo-0.0.1-SNAPSHOT.jar > app.log 2>&1 < /dev/null")
    print("等 35 秒启动...")
    time.sleep(35)
    
    print("\n>>> 7. 检查启动日志")
    run(c, f"tail -15 {REMOTE_ROOT}/app.log", timeout=15)
    
    c.close()
    print("\n>>> 部署完成！浏览器访问 http://192.168.92.128:8080/")

if __name__ == "__main__":
    main()

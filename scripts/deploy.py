# -*- coding: utf-8 -*-
"""部署招聘网站到虚拟机：SFTP 上传 Java + 前端 + mvn 打包 + 启动。

连接参数（地址 / 用户 / 密码）取自 config/local.env（不入库），
模板见 config/local.env.example。
"""
import paramiko
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

HOST = config.VM_HOST
USER = config.VM_SSH_USER
PASS = config.VM_SSH_PASSWORD
REMOTE_ROOT = os.environ.get("VM_REMOTE_ROOT", "/home/" + USER + "/day08")
LOCAL_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "day08")

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
    
    # 确保远程目录结构
    print("\n>>> 2. 上传 Java 源码")
    java_base = os.path.join(LOCAL_ROOT, "src", "main", "java", "com", "example", "demo")
    remote_java = f"{REMOTE_ROOT}/src/main/java/com/example/demo"
    
    # 上传 service 目录
    for f in os.listdir(os.path.join(java_base, "service")):
        lp = os.path.join(java_base, "service", f)
        rp = f"{remote_java}/service/{f}"
        print(f"  {rp}")
        sftp.put(lp, rp)
    
    # 上传 controller 目录
    for f in os.listdir(os.path.join(java_base, "controller")):
        lp = os.path.join(java_base, "controller", f)
        rp = f"{remote_java}/controller/{f}"
        print(f"  {rp}")
        sftp.put(lp, rp)
    
    # 上传 config 目录
    for f in os.listdir(os.path.join(java_base, "config")):
        lp = os.path.join(java_base, "config", f)
        rp = f"{remote_java}/config/{f}"
        print(f"  {rp}")
        sftp.put(lp, rp)
    
    # 上传 util 目录（新建）
    util_local = os.path.join(java_base, "util")
    util_remote = f"{remote_java}/util"
    try: sftp.stat(util_remote)
    except: sftp.mkdir(util_remote)
    for f in os.listdir(util_local):
        lp = os.path.join(util_local, f)
        rp = f"{util_remote}/{f}"
        print(f"  {rp}")
        sftp.put(lp, rp)
    
    # 上传 filter 目录（新建）
    filter_local = os.path.join(java_base, "filter")
    filter_remote = f"{remote_java}/filter"
    try: sftp.stat(filter_remote)
    except: sftp.mkdir(filter_remote)
    for f in os.listdir(filter_local):
        lp = os.path.join(filter_local, f)
        rp = f"{filter_remote}/{f}"
        print(f"  {rp}")
        sftp.put(lp, rp)
    
    # 上传 pom.xml
    print(f"  {REMOTE_ROOT}/pom.xml")
    sftp.put(os.path.join(LOCAL_ROOT, "pom.xml"), f"{REMOTE_ROOT}/pom.xml")
    
    # 上传前端 static 目录
    print("\n>>> 3. 上传前端文件")
    static_local = os.path.join(LOCAL_ROOT, "src", "main", "resources", "static")
    static_remote = f"{REMOTE_ROOT}/src/main/resources/static"
    
    # 上传 HTML 文件
    for f in os.listdir(static_local):
        if f.endswith(".html"):
            print(f"  {static_remote}/{f}")
            sftp.put(os.path.join(static_local, f), f"{static_remote}/{f}")
    
    # 上传 app.js
    print(f"  {static_remote}/app.js")
    sftp.put(os.path.join(static_local, "app.js"), f"{static_remote}/app.js")
    
    # 上传 css 目录
    css_local = os.path.join(static_local, "css")
    css_remote = f"{static_remote}/css"
    try: sftp.stat(css_remote)
    except: sftp.mkdir(css_remote)
    for f in os.listdir(css_local):
        print(f"  {css_remote}/{f}")
        sftp.put(os.path.join(css_local, f), f"{css_remote}/{f}")
    
    # 上传 js 目录（跳过 echarts）
    js_local = os.path.join(static_local, "js")
    js_remote = f"{static_remote}/js"
    try: sftp.stat(js_remote)
    except: sftp.mkdir(js_remote)
    for f in os.listdir(js_local):
        if "echarts" in f:
            print(f"  跳过 {f}（VM 已有）")
            continue
        print(f"  {js_remote}/{f}")
        sftp.put(os.path.join(js_local, f), f"{js_remote}/{f}")
    
    sftp.close()
    
    # 杀旧进程 + 打包 + 启动
    print("\n>>> 4. 杀旧进程")
    run(c, "pkill -f demo-0.0.1-SNAPSHOT.jar 2>/dev/null; sleep 2; echo killed", timeout=15)
    
    print("\n>>> 5. Maven 打包")
    run(c, f"cd {REMOTE_ROOT} && export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 && "
            "export PATH=$JAVA_HOME/bin:$PATH && mvn clean package -DskipTests 2>&1 | tail -20", timeout=600)
    
    print("\n>>> 6. 启动 Spring Boot")
    fire(c, f"cd {REMOTE_ROOT} && export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 && "
            "export PATH=$JAVA_HOME/bin:$PATH && "
            "nohup java -jar target/demo-0.0.1-SNAPSHOT.jar > app.log 2>&1 < /dev/null; echo STARTED")
    print("等 35 秒启动...")
    time.sleep(35)
    
    print("\n>>> 7. 检查启动日志")
    run(c, f"tail -15 {REMOTE_ROOT}/app.log", timeout=15)
    
    c.close()
    print(f"\n>>> 部署完成！浏览器访问 http://{HOST}:{config.VM_BACKEND_PORT}/")

if __name__ == "__main__":
    main()

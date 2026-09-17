# -*- coding: utf-8 -*-
"""SSH 工具: 远程执行命令 + 文件传输"""
import paramiko, os

class SSHHelper:
    def __init__(self, host="192.168.92.128", user="xiaoliyu", password="123456"):
        self.host = host
        self.user = user
        self.password = password
        self.ssh = None

    def connect(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.host, username=self.user, password=self.password)

    def run(self, cmd):
        if not self.ssh:
            self.connect()
        stdin, stdout, stderr = self.exec_command(cmd)
        return stdout.read().decode(), stderr.read().decode()

    def exec_command(self, cmd):
        return self.ssh.exec_command(cmd)

    def upload(self, local, remote):
        if not self.ssh:
            self.connect()
        sftp = self.ssh.open_sftp()
        sftp.put(local, remote)
        sftp.close()

    def close(self):
        if self.ssh:
            self.ssh.close()

if __name__ == "__main__":
    ssh = SSHHelper()
    ssh.connect()
    out, err = ssh.run("hostname && whoami && jps")
    print(out)
    ssh.close()

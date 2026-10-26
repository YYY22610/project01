"""服务器部署辅助工具（paramiko）。

用法：
    python deploy_remote.py check      # 查看服务器上 /opt/app 现状
    python deploy_remote.py run "<命令>"  # 在服务器执行命令
    python deploy_remote.py put <本地路径> <远端路径>   # 上传文件
"""
import sys

import paramiko

HOST = "47.114.33.223"
USER = "root"
PWD = "SSyz:020617"


def connect() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=25, banner_timeout=30)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 120) -> tuple[int, str]:
    _in, out, err = c.exec_command(cmd, timeout=timeout, get_pty=False)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    return code, (o + e).strip()


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    c = connect()
    try:
        if action == "run":
            code, txt = run(c, sys.argv[2])
            print(txt)
            print(f"[exit {code}]")
        elif action == "put":
            sftp = c.open_sftp()
            sftp.put(sys.argv[2], sys.argv[3])
            sftp.close()
            print(f"已上传 {sys.argv[2]} -> {sys.argv[3]}")
        else:
            for label, cmd in [
                ("应用目录", "ls -la /opt/app | head -20"),
                ("是否 git 仓库", "ls -d /opt/app/.git 2>/dev/null || echo '不是 git 仓库'"),
                ("服务状态", "systemctl is-active travel-backend nginx 2>&1"),
                ("后端进程", "ps aux | grep -E 'uvicorn|gunicorn' | grep -v grep | head -5"),
                ("数据库", "sudo -u postgres psql -d travel_experiment -tAc \"select 'users='||count(*) from users\" 2>&1"),
                ("磁盘", "df -h / | tail -1"),
            ]:
                code, txt = run(c, cmd)
                print(f"===== {label} (exit {code}) =====")
                print(txt)
                print()
    finally:
        c.close()


if __name__ == "__main__":
    main()

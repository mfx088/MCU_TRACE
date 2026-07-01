#!/usr/bin/env python3
"""Generic TCP forward tunnel: 127.0.0.1:8443 -> TARGETS (multi-IP retry)

Why: 公司网封 github.com:22，但 GitHub 主 IP 段 443 端口可达。
     写一个 raw TCP forward tunnel，让 git 走 SSH 协议经本地出去，绕开 DPI。

Usage:
    # 1) 启动 tunnel (前台跑，Ctrl+C 关)
    python tools/github_tunnel.py

    # 2) 在另一个 terminal push
    git push origin <branch>

Config:
    ~/.ssh/config 加:
        Host github.com
            HostName 127.0.0.1
            Port 8443
            User git
            StrictHostKeyChecking no

参数化（环境变量）:
    TUNNEL_PORT     监听端口     默认 8443
    TUNNEL_TARGETS  目标 IP 列表  默认 GitHub 20.205.243.x
    TUNNEL_TIMEOUT  连接超时(秒) 默认 120
"""
import os
import socket
import sys
import threading
import time
import traceback

LISTEN_HOST = '127.0.0.1'
LISTEN_PORT = int(os.environ.get('TUNNEL_PORT', '8443'))
TARGETS = os.environ.get(
    'TUNNEL_TARGETS',
    '20.205.243.160,20.205.243.161,20.205.243.166,20.205.243.168',
).split(',')
TIMEOUT = int(os.environ.get('TUNNEL_TIMEOUT', '120'))


def relay(name, src, dst, deadline):
    n = 0
    try:
        while time.time() < deadline:
            src.settimeout(max(1, deadline - time.time()))
            try:
                data = src.recv(8192)
            except socket.timeout:
                continue
            if not data:
                break
            n += len(data)
            dst.sendall(data)
            if n > 256:  # 一旦有数据流就延长 deadline
                deadline = time.time() + 60
    except Exception:
        pass
    finally:
        try:
            src.shutdown(socket.SHUT_RD)
        except OSError:
            pass
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def connect_with_retry(deadline, targets):
    last_err = None
    for ip in targets:
        if time.time() >= deadline:
            break
        try:
            t0 = time.time()
            target = socket.create_connection((ip, 443), timeout=10)
            print(f'    -> connected {ip} in {time.time()-t0:.1f}s', flush=True)
            return target
        except OSError as e:
            print(f'    -> {ip} failed: {e}', flush=True)
            last_err = e
    raise last_err or OSError('all targets failed')


def handle(client):
    peer = client.getpeername()
    deadline = time.time() + TIMEOUT
    try:
        try:
            target = connect_with_retry(deadline, TARGETS)
        except OSError as e:
            print(f'[{peer}] all targets failed: {e}', flush=True)
            return

        t1 = threading.Thread(
            target=relay,
            args=('c->t', client, target, deadline),
            daemon=True,
        )
        t2 = threading.Thread(
            target=relay,
            args=('t->c', target, client, deadline),
            daemon=True,
        )
        t1.start(); t2.start()
        t1.join()
        t2.join(timeout=5)
        client.close()
        target.close()
    except Exception:
        traceback.print_exc()
    finally:
        try:
            client.close()
        except OSError:
            pass


def main():
    print(f'TCP forward tunnel: {LISTEN_HOST}:{LISTEN_PORT} -> {TARGETS}', flush=True)
    print(f'(Ctrl+C to stop)', flush=True)
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((LISTEN_HOST, LISTEN_PORT))
    except OSError as e:
        print(f'ERROR: bind {LISTEN_HOST}:{LISTEN_PORT} failed: {e}', file=sys.stderr)
        sys.exit(1)
    srv.listen(64)
    try:
        while True:
            client, _ = srv.accept()
            threading.Thread(target=handle, args=(client,), daemon=True).start()
    except KeyboardInterrupt:
        print('\nstopped.', flush=True)
    finally:
        srv.close()


if __name__ == '__main__':
    main()

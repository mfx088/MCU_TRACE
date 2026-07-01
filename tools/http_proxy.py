#!/usr/bin/env python3
"""
http_proxy.py - 本地 HTTP CONNECT 代理（公司网绕封 GitHub 用）

[原理]
  GitHub SSH 拒绝 direct-tcpip channel（所以 -D SOCKS 不行）。
  但本工具是一个普通 HTTP CONNECT 代理：
    1) 浏览器配 HTTP 代理为 127.0.0.1:8444
    2) 浏览器发 "CONNECT github.com:443 HTTP/1.1"
    3) 本代理解析 host:port，连接 GitHub IP 段 20.205.243.x:443
    4) 双向转发 raw bytes

[配合]
  先启动 tools/github_tunnel.py（监听 127.0.0.1:8443 → 20.205.243.x:443）
  再启动本工具（监听 127.0.0.1:8444，做 HTTP CONNECT 解析）

[使用]
  浏览器代理设置:
    HTTP  127.0.0.1:8444
    HTTPS 127.0.0.1:8444
  然后浏览器访问 https://github.com 应该正常

[安全]
  仅允许 CONNECT 到本工具配置的 ALLOWED_HOSTS（默认 github.com / *.github.com / api.github.com）
  其他 host 直接拒绝连接，防止成为开放代理
"""
import os
import socket
import sys
import threading
import time

LISTEN_HOST = '127.0.0.1'
LISTEN_PORT = int(os.environ.get('HTTP_PROXY_PORT', '8444'))

# GitHub 主 IP 段（公司网可达）
GITHUB_IPS = [
    '20.205.243.160', '20.205.243.161', '20.205.243.166', '20.205.243.168',
    '140.82.114.4', '140.82.114.5', '140.82.114.6',
    '140.82.112.3', '140.82.112.4',
]

# 白名单 host（防止成为开放代理）
ALLOWED_HOSTS = (
    'github.com', 'www.github.com', 'api.github.com',
    'raw.githubusercontent.com', 'codeload.github.com',
    'objects.githubusercontent.com', 'user-images.githubusercontent.com',
    'avatars.githubusercontent.com', 'gist.github.com',
    '*.githubusercontent.com',
)


def host_allowed(host: str) -> bool:
    """Check if host is in whitelist."""
    host = host.lower()
    if host in ALLOWED_HOSTS:
        return True
    for pat in ALLOWED_HOSTS:
        if pat.startswith('*.'):
            if host.endswith(pat[1:]):
                return True
    return False


def connect_to_github(port: int = 443) -> socket.socket:
    """Try multiple GitHub IPs, return first successful connection."""
    last_err = None
    for ip in GITHUB_IPS:
        try:
            t0 = time.time()
            sock = socket.create_connection((ip, port), timeout=10)
            print(f'    -> connected {ip}:{port} in {time.time()-t0:.1f}s', flush=True)
            return sock
        except OSError as e:
            print(f'    -> {ip}:{port} failed: {e}', flush=True)
            last_err = e
    raise last_err or OSError('all GitHub IPs failed')


def relay(src, dst, name):
    """Bidirectional byte forward."""
    try:
        while True:
            data = src.recv(8192)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        for s in (src, dst):
            try: s.shutdown(socket.SHUT_RDWR)
            except OSError: pass


def handle(client):
    """One HTTP CONNECT proxy session."""
    peer = client.getpeername()
    try:
        client.settimeout(10)
        # Read HTTP CONNECT request
        request = b''
        while b'\r\n\r\n' not in request:
            chunk = client.recv(4096)
            if not chunk:
                client.close()
                return
            request += chunk
            if len(request) > 8192:
                client.sendall(b'HTTP/1.1 400 Bad Request\r\n\r\n')
                client.close()
                return

        first_line = request.split(b'\r\n', 1)[0].decode('latin-1', errors='replace')
        print(f'[{peer}] {first_line}', flush=True)

        if not first_line.startswith('CONNECT '):
            # Only support CONNECT (HTTPS proxy mode)
            client.sendall(b'HTTP/1.1 405 Method Not Allowed\r\n\r\n')
            client.close()
            return

        # Parse "CONNECT host:port HTTP/1.1"
        parts = first_line.split()
        if len(parts) < 3:
            client.sendall(b'HTTP/1.1 400 Bad Request\r\n\r\n')
            client.close()
            return

        target = parts[1]
        if ':' in target:
            host, port_s = target.rsplit(':', 1)
            try: port = int(port_s)
            except ValueError: port = 443
        else:
            host, port = target, 443

        # Whitelist check
        if not host_allowed(host):
            print(f'[{peer}] BLOCKED {host} (not in whitelist)', flush=True)
            client.sendall(b'HTTP/1.1 403 Forbidden\r\n\r\n')
            client.close()
            return

        print(f'[{peer}] → {host}:{port}', flush=True)

        # Connect to GitHub IP
        try:
            upstream = connect_to_github(port if port in (80, 443) else 443)
        except OSError as e:
            print(f'[{peer}] all GitHub IPs failed: {e}', flush=True)
            client.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
            client.close()
            return

        # Tell client "200 Connection Established"
        client.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        client.settimeout(None)

        # Bidirectional relay
        t1 = threading.Thread(target=relay, args=(client, upstream, 'c→u'), daemon=True)
        t2 = threading.Thread(target=relay, args=(upstream, client, 'u→c'), daemon=True)
        t1.start(); t2.start()
        t1.join()
        t2.join(timeout=2)
        client.close()
        upstream.close()
    except Exception as e:
        print(f'[{peer}] error: {e}', flush=True)
        try: client.close()
        except OSError: pass


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(32)
    print(f'HTTP CONNECT proxy: {LISTEN_HOST}:{LISTEN_PORT}', flush=True)
    print(f'  → GitHub IPs: {GITHUB_IPS}', flush=True)
    print(f'  → Allowed hosts: {", ".join(ALLOWED_HOSTS)}', flush=True)
    print('Configure browser: HTTP/HTTPS proxy = 127.0.0.1:8444', flush=True)
    print('(Ctrl+C to stop)', flush=True)
    try:
        while True:
            client, _ = server.accept()
            threading.Thread(target=handle, args=(client,), daemon=True).start()
    except KeyboardInterrupt:
        print('\nshutting down...', flush=True)
    finally:
        server.close()


if __name__ == '__main__':
    main()

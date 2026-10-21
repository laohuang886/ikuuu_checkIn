# -*- coding: utf-8 -*-
"""
把本地 Cookie 加密上传为 GitHub Actions Secret（IKUUU_COOKIE）

用法：
    set GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxx
    python upload_secret.py

可选参数：
    python upload_secret.py --repo 995william/ikuuu_checkIn --name IKUUU_COOKIE --file local_cookie.txt

依赖：pip install requests pynacl
"""

import os
import sys
import base64
import argparse
import requests

try:
    from nacl import encoding, public
    HAS_NACL = True
except ImportError:
    HAS_NACL = False

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def upload(repo: str, token: str, name: str, value: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    r = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers, timeout=20
    )
    if r.status_code == 401:
        print("[X] Token 无效或已过期（401）")
        return False
    if r.status_code == 404:
        print(f"[X] 仓库不存在或 Token 无权访问: {repo}（404）")
        return False
    if r.status_code != 200:
        print(f"[X] 获取公钥失败 {r.status_code}: {r.text[:200]}")
        return False

    pk = r.json()
    public_key = public.PublicKey(pk["key"].encode("utf-8"), encoding.Base64Encoder())
    sealed = public.SealedBox(public_key).encrypt(value.encode("utf-8"))
    payload = {
        "encrypted_value": base64.b64encode(sealed).decode("utf-8"),
        "key_id": pk["key_id"],
    }

    r2 = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
        headers=headers, json=payload, timeout=20
    )
    if r2.status_code in (201, 204):
        print(f"[OK] Secret [{name}] 已写入仓库 {repo}")
        return True
    print(f"[X] 写入失败 {r2.status_code}: {r2.text[:200]}")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default='995william/ikuuu_checkIn')
    ap.add_argument('--name', default='IKUUU_COOKIE')
    ap.add_argument('--file', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_cookie.txt'))
    ap.add_argument('--token', default=None)
    args = ap.parse_args()

    token = args.token or os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_PAT')
    if not token:
        print("[X] 未提供 Token，请设置环境变量 GITHUB_TOKEN 或用 --token 传入")
        sys.exit(1)
    if not HAS_NACL:
        print("[X] 缺少 PyNaCl，请先执行: pip install pynacl")
        sys.exit(1)
    if not os.path.isfile(args.file):
        print(f"[X] 找不到 Cookie 文件: {args.file}")
        sys.exit(1)

    value = open(args.file, encoding='utf-8').read().strip()
    if not value or '=' not in value:
        print("[X] Cookie 文件内容为空或格式不对")
        sys.exit(1)

    print(f"仓库: {args.repo} | Secret: {args.name} | Cookie 长度: {len(value)}")
    ok = upload(args.repo, token.strip(), args.name, value)
    sys.exit(0 if ok else 2)


if __name__ == '__main__':
    main()

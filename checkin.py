# -*- coding: utf-8 -*-
"""
iKuuu 自动签到（GitHub Actions / 本地通用）

依赖环境变量：
    IKUUU_COOKIE   登录 Cookie（必填）
                   单账号：a=1; b=2; c=3
                   多账号：一行一个账号的 Cookie（GitHub Secret 支持多行）
    IKUUU_BASE_URL 站点地址，默认 https://ikuuu.top

退出码：
    0 = 全部账号处理完成（含"今天已签到"这类正常情况）
    1 = 没有任何可用 Cookie
    2 = 存在 Cookie 失效 / 请求异常的账号
"""

import os
import sys
import json
import requests

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)

BASE_URL = (os.environ.get('IKUUU_BASE_URL') or 'https://ikuuu.top').rstrip('/')
CHECKIN_URL = f'{BASE_URL}/user/checkin'

# 服务端明确表示未登录 / Cookie 过期时的关键词
EXPIRED_KEYS = ('未登录', '请登录', '登录已失效', '重新登录', 'token', 'Unauthorized')


def split_cookies(raw: str):
    """支持多账号：换行分隔优先；单账号则是标准的 a=1; b=2 形式"""
    if not raw:
        return []
    if '\n' in raw:
        items = [line.strip() for line in raw.splitlines()]
    else:
        items = [raw.strip()]
    return [x for x in items if x and '=' in x]


def checkin(cookie: str, index: int, total: int):
    session = requests.Session()
    session.headers.update({
        'User-Agent': USER_AGENT,
        'Cookie': cookie,
        'Referer': f'{BASE_URL}/user',
        'Origin': BASE_URL,
        'Accept': 'application/json, text/plain, */*',
        'X-Requested-With': 'XMLHttpRequest',
    })

    tag = f'[{index}/{total}]'
    try:
        resp = session.post(CHECKIN_URL, timeout=30)
    except Exception as e:
        print(f'{tag} 请求失败: {e}')
        return 'error'

    if resp.status_code != 200:
        print(f'{tag} HTTP {resp.status_code}: {resp.text[:120]}')
        return 'error'

    try:
        data = resp.json()
    except ValueError:
        if '/auth/login' in resp.url:
            print(f'{tag} Cookie 已失效，被重定向到登录页')
            return 'expired'
        print(f'{tag} 返回非 JSON: {resp.text[:120]}')
        return 'error'

    ret = data.get('ret')
    msg = (data.get('msg') or data.get('message') or '').strip()

    if ret == 1:
        print(f'{tag} 签到成功: {msg}')
        return 'ok'
    if ret == 0:
        if any(k.lower() in msg.lower() for k in EXPIRED_KEYS):
            print(f'{tag} Cookie 失效: {msg}')
            return 'expired'
        print(f'{tag} 无需重复签到: {msg}')
        return 'ok'
    print(f'{tag} 未知响应 ret={ret}: {msg or json.dumps(data, ensure_ascii=False)[:120]}')
    return 'error'


def main():
    raw = os.environ.get('IKUUU_COOKIE', '').strip()
    cookies = split_cookies(raw)
    if not cookies:
        print('[X] 未检测到 IKUUU_COOKIE，请在环境变量或仓库 Secret 中配置登录 Cookie')
        sys.exit(1)

    print(f'站点: {BASE_URL} | 账号数: {len(cookies)}')
    results = [checkin(c, i + 1, len(cookies)) for i, c in enumerate(cookies)]

    bad = [r for r in results if r in ('error', 'expired')]
    print('=' * 50)
    print(f'汇总: 完成 {len(results) - len(bad)} / {len(results)}')
    sys.exit(2 if bad else 0)


if __name__ == '__main__':
    main()

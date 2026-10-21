# -*- coding: utf-8 -*-
"""
iKuuu 登录辅助工具（本地运行）

用途：
当站点开启图片点选/滑动验证码等强风控时，无头自动化往往难以稳定通过。
本工具在本地启动真实浏览器（有头模式，使用系统已安装的 Edge），自动预填账号密码，
由人工在桌面窗口中完成一次图片点选验证，脚本自动抓取并导出长期有效的登录 Cookie。

支持：
1. 桌面弹出真实浏览器，自动填好账号密码
2. 自动捕获登录成功的完整 Cookie
3. 本地验证 Cookie 有效性并预览流量数据
4. （可选）一键加密同步至 GitHub Actions Secrets (IKUUU_COOKIE)

用法：
    python login_helper.py                      # 不预填，自己在浏览器里输入
    python login_helper.py <邮箱> <密码>         # 自动预填，只需完成验证 + 点登录
    set IKUUU_EMAIL=xxx && set IKUUU_PASSWORD=yyy && python login_helper.py
"""

import os
import re
import sys
import time
import base64
import requests
from playwright.sync_api import sync_playwright

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

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)

BASE_URL = "https://ikuuu.top"


def format_cookies(cookies_list):
    """将 Playwright cookies 列表格式化为标准的 Cookie 请求头字符串"""
    parts = []
    for c in cookies_list:
        name = c.get('name')
        val = c.get('value')
        if name and val:
            parts.append(f"{name}={val}")
    return "; ".join(parts)


def verify_cookie(cookie_str, base_url=BASE_URL):
    """用抓到的 Cookie 请求用户中心，确认是否有效并提取流量信息"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': USER_AGENT,
        'Cookie': cookie_str,
        'Referer': base_url + '/user',
    })
    try:
        resp = session.get(base_url + '/user', timeout=20)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        print(f"[!] Cookie 验证请求失败: {e}")
        return False, None

    if '/auth/login' in resp.url or ('登录' in html and '退出' not in html):
        return False, None

    info = {}
    # 流量信息：常见写法 "已用 12.34GB / 总量 100GB" 或剩余流量
    m = re.search(r'([\d.]+\s*[KMGT]B)\s*/\s*([\d.]+\s*[KMGT]B)', html)
    if m:
        info['used'] = m.group(1)
        info['total'] = m.group(2)
    m2 = re.search(r'剩余[^<]{0,20}?([\d.]+\s*[KMGT]B)', html)
    if m2:
        info['remain'] = m2.group(1)
    m3 = re.search(r'(\d+)\s*天', html)
    if m3:
        info['days'] = m3.group(1)
    return True, info


def upload_secret_to_github(repo, token, secret_name, secret_value):
    """自动使用公钥加密并将 Secret 同步至 GitHub Actions"""
    if not HAS_NACL:
        print("[!] 未安装 PyNaCl，跳过自动同步 GitHub Secrets")
        return False
    try:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        pk_url = f"https://api.github.com/repos/{repo}/actions/secrets/public-key"
        r = requests.get(pk_url, headers=headers, timeout=15)
        r.raise_for_status()
        pk_info = r.json()

        public_key = public.PublicKey(pk_info["key"].encode("utf-8"), encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

        set_url = f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}"
        payload = {"encrypted_value": encrypted_b64, "key_id": pk_info["key_id"]}
        r_put = requests.put(set_url, json=payload, headers=headers, timeout=15)
        r_put.raise_for_status()
        print(f"[OK] 成功同步 Secret [{secret_name}] 至 GitHub 仓库 {repo}！")
        return True
    except Exception as e:
        print(f"[!] 同步 GitHub Secret 失败: {e}")
        return False


def launch_browser(p):
    """优先用系统 Edge（本机未下载 Playwright 内置 Chromium）"""
    try:
        return p.chromium.launch(
            channel="msedge",
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
    except Exception as e:
        print(f"[!] 使用系统 Edge 启动失败（{e}），尝试内置 Chromium ...")
        return p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )


def interactive_login(email=None, passwd=None, base_url=BASE_URL,
                      gh_token=None, gh_repo="995william/ikuuu_checkIn",
                      timeout=300):
    email = email or os.environ.get('IKUUU_EMAIL') or ''
    passwd = passwd or os.environ.get('IKUUU_PASSWORD') or ''
    gh_token = gh_token or os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_PAT') or ''

    print("=" * 62)
    print("iKuuu 桌面端辅助登录工具启动")
    print("=" * 62)
    print(f"目标站点: {base_url}")
    print(f"账号: {email or '（未指定，请在浏览器窗口中手动输入）'}")
    print("即将弹出浏览器窗口，请在窗口中完成验证并登录。")
    print("=" * 62)

    login_url = f"{base_url.rstrip('/')}/auth/login"
    cookie_str = ""

    with sync_playwright() as p:
        browser = launch_browser(p)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
            locale="zh-CN"
        )
        page = context.new_page()

        try:
            page.goto(login_url, wait_until='domcontentloaded')
            if email:
                try:
                    page.fill('#email', email)
                except Exception:
                    pass
            if passwd:
                try:
                    page.fill('#password', passwd)
                except Exception:
                    pass
            if email and passwd:
                print("[提示] 账号与密码已自动填入！")
            else:
                print("[提示] 请在页面上输入账号密码")
            print(">>> 请在浏览器窗口中：完成图片验证 -> 点击登录")
            print(f">>> 脚本最长等待 {timeout} 秒 ...\n")

            page.wait_for_url("**/user**", timeout=timeout * 1000)
            print("[OK] 检测到已成功登录进入用户中心！")
            time.sleep(2)

            pw_cookies = context.cookies()
            cookie_str = format_cookies(pw_cookies)

            out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_cookie.txt")
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(cookie_str)
            print(f"[OK] 登录 Cookie 已保存至: {out_file}")

            masked = cookie_str[:20] + "******" if len(cookie_str) > 30 else "***"
            print(f"[预览] {masked}  (总长度: {len(cookie_str)})")

            ok, info = verify_cookie(cookie_str, base_url)
            print(f"[验证] Cookie 有效性: {'有效' if ok else '无效/已失效'}")
            if ok and info:
                print(f"[账户] {info}")

            if ok and gh_token:
                upload_secret_to_github(gh_repo, gh_token, "IKUUU_COOKIE", cookie_str)
            elif ok:
                print("[提示] 未提供 GITHUB_TOKEN，跳过自动同步；请手动把 Cookie 填到仓库 Secret: IKUUU_COOKIE")

        except Exception as e:
            print(f"[X] 登录等待超时或出错: {e}")
        finally:
            try:
                browser.close()
            except Exception:
                pass

    return cookie_str


if __name__ == "__main__":
    test_email = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('IKUUU_EMAIL')
    test_pwd = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('IKUUU_PASSWORD')
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
    interactive_login(test_email, test_pwd, gh_token=token)

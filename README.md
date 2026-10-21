# iKuuu 自动签到

基于 GitHub Actions 的 iKuuu（v2board 面板）每日自动签到，无需服务器，Cookie 一次配置后长期运行。

## 目录结构

```
ikuuu-checkin/
├── checkin.py                    # 签到主脚本（GitHub Actions / 本地通用）
├── login_helper.py               # 桌面浏览器辅助登录，用于抓取登录 Cookie
├── requirements.txt              # 依赖：requests
├── local_cookie.txt              # 本地抓取的 Cookie（已被 .gitignore 忽略，勿提交）
└── .github/workflows/checkin.yml # 定时任务：每天 08:30 / 20:30（北京时间）
```

## 零、把代码推到你的仓库

本地仓库已初始化并完成首次提交（`local_cookie.txt` 已被 `.gitignore` 排除，不会误提交）。
接上你自己的远端仓库：

```bash
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git branch -M main
git push -u origin main
```

推送完成后再继续下面的 Secret 配置。

## 一、抓取登录 Cookie

站点有图片点选验证码，无头脚本过不去，所以走"真人在浏览器里登录一次"的方式：

```bash
pip install playwright requests pynacl
python login_helper.py                    # 自己在弹出的窗口里输账号密码
python login_helper.py <邮箱> <密码>       # 或让脚本预填，只做验证 + 点登录
```

完成后：
- Cookie 写入 `local_cookie.txt`
- 脚本自动请求 `/user` 校验 Cookie 是否有效
- 若设置了环境变量 `GITHUB_TOKEN`（需 repo 权限），会自动加密同步为仓库 Secret `IKUUU_COOKIE`

> 本机未下载 Playwright 内置 Chromium，脚本优先用系统 Edge 启动（`channel="msedge"`）。

## 二、配置仓库 Secret

进入仓库 `Settings → Secrets and variables → Actions → New repository secret`：

| Name | Value |
| --- | --- |
| `IKUUU_COOKIE` | `local_cookie.txt` 的全部内容 |
| `IKUUU_BASE_URL` | `https://ikuuu.top`（可选，域名变更时用） |

多账号：`IKUUU_COOKIE` 按**一行一个账号**填写即可，脚本会逐个签到并汇总。

## 三、运行

- 自动：Actions 每天 08:30、20:30（北京时间）执行
- 手动：仓库 `Actions → iKuuu 自动签到 → Run workflow`
- 本地：`IKUUU_COOKIE="$(cat local_cookie.txt)" python checkin.py`

## 签到结果说明

调用 `POST https://ikuuu.top/user/checkin`，返回 JSON：

| ret | 含义 | 处理 |
| --- | --- | --- |
| `1` | 签到成功，返回获得流量 | 记为成功 |
| `0` | 今天已签到，或 Cookie 失效 | 按 msg 关键词区分，失效会提示 |

脚本退出码：`0` 全部正常；`1` 没配 Cookie；`2` 存在失效或异常账号（方便 Actions 里判断失败）。

## 注意事项

- Cookie 有效期通常较长，但改密码、退出登录后需重新抓取。
- `local_cookie.txt` 已在 `.gitignore` 中，切勿提交到公开仓库。
- 免费公开的 GitHub 仓库若长期无 commit，Actions 定时可能被平台停用；可以偶尔手动触发一次。

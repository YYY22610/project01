"""部署证明材料截图脚本：登录页 + 后台核心功能页。
产出到 browser_shots/deploy_proof/。
"""
import os
import sys

from playwright.sync_api import sync_playwright

FRONTEND = "http://47.114.33.223"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_shots", "deploy_proof")
CHROME = r"C:\Users\27475\.agent-browser\browsers\chrome-152.0.7977.64\chrome.exe"

ADMIN_PAGES = [
    ("dashboard", "/admin/dashboard"),
    ("participants", "/admin/participants"),
    ("submissions", "/admin/submissions"),
    ("questionnaire", "/admin/questionnaire"),
    ("logs", "/admin/logs"),
    ("settings", "/admin/settings"),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))

        # 1) 后台登录页
        page.goto(f"{FRONTEND}/admin/login", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(OUT, "01_admin_login.png"), full_page=True)
        print("[ok] 01 后台登录页")

        # 2) 管理员登录
        try:
            page.fill('input[type="text"], input[name="username"], input[placeholder*="用户名"], input[placeholder*="账号"]', "admin")
            page.fill('input[type="password"]', "Admin2026")
            page.wait_for_timeout(300)
            page.screenshot(path=os.path.join(OUT, "02_admin_login_filled.png"), full_page=True)
            page.click('button[type="submit"]')
            page.wait_for_timeout(3000)
            print("[ok] 02 管理员登录，当前路径:", page.url)
        except Exception as e:
            print("[warn] 登录交互异常:", str(e)[:200])

        # 3) 各后台功能页
        for i, (name, path) in enumerate(ADMIN_PAGES, start=3):
            try:
                page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(1500)
                fn = os.path.join(OUT, f"{i:02d}_admin_{name}.png")
                page.screenshot(path=fn, full_page=True)
                print(f"[ok] {i:02d} {name} -> {page.url}")
            except Exception as e:
                print(f"[warn] {i:02d} {name} 截图失败: {str(e)[:200]}")
                errors.append(f"{name}:{str(e)[:120]}")

        browser.close()

    print("\n截图目录:", OUT)
    print("文件:")
    for f in sorted(os.listdir(OUT)):
        print("  -", f)
    if errors:
        print("\n页面错误:")
        for e in errors:
            print("  *", e)


if __name__ == "__main__":
    sys.exit(main() and 0)
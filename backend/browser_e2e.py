"""MOA 群辩真实浏览器端到端点击验证（Playwright 驱动 Chrome）。

流程：登录 -> 演示 -> 任务页 -> 展开讨论室 -> 发首条偏好触发 SSE
-> 专家流式发言 -> 主持人反问(await_user, 输入框应为可编辑) -> 回填回答(resume)
-> 确认门(await_confirm, 输入框应为可编辑) -> 确认 -> 最终方案渲染 + 导出 Word(可点击) -> 下载。

状态判定以「讨论室输入框 placeholder」为准（精确、稳定，规避「导出 Word」按钮常驻 DOM 的误判）：
  - 默认/空闲: "说说你的旅行偏好，如：喜欢人文和美食，预算紧"
  - 群聊中:     "智囊团讨论中…"
  - 反问等待:   "输入你的回答…"
  - 确认门等待: "输入「确认」或你的修改意见…"
"""
import os
import time
from playwright.sync_api import sync_playwright

CHROME = r"C:\Users\27475\.agent-browser\browsers\chrome-152.0.7977.64\chrome.exe"
BASE = "http://127.0.0.1:5173"
EMAIL = "moaval@test.com"
PW = "Test1234!"
SHOT = r"D:\27475\WorkBuddy-搭建网站\travel-experiment-platform\browser_shots"
os.makedirs(SHOT, exist_ok=True)

PREF_IDLE = "说说你的旅行偏好，如：喜欢人文和美食，预算紧"
PREF_THINKING = "智囊团讨论中…"
PREF_USER = "输入你的回答…"
PREF_CONFIRM = "输入「确认」或你的修改意见…"


def log(*a):
    print("[E2E]", *a, flush=True)


KNOWN_PH = {PREF_IDLE, PREF_THINKING, PREF_USER, PREF_CONFIRM}


def chat_placeholder(page):
    """返回讨论室输入框当前 placeholder；只认四个已知值，避免误取页面其他输入框。"""
    for inp in page.query_selector_all('input[placeholder]'):
        ph = inp.get_attribute('placeholder') or ''
        if ph in KNOWN_PH:
            return ph
    return ''


steps = {}

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=CHROME,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    page.set_default_timeout(20000)
    page.on("console", lambda m: log("console", m.type, m.text[:160]))
    page.on("pageerror", lambda e: log("pageerror", str(e)[:200]))

    # 1) 登录
    page.goto(BASE + "/register", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    page.screenshot(path=os.path.join(SHOT, "01_register.png"))
    try:
        if page.get_by_text("去登录").count() > 0:
            page.get_by_text("去登录").first.click()
            time.sleep(0.5)
    except Exception as e:
        log("switch-to-login warn:", e)
    email = page.get_by_placeholder("请输入邮箱")
    email.wait_for(state="visible", timeout=10000)
    email.fill(EMAIL)
    try:
        pw = page.get_by_placeholder("请输入密码")
        if pw.count() > 0:
            pw.first.fill(PW)
    except Exception:
        pass
    btn = page.get_by_role("button").filter(has_text="登录")
    btn.wait_for(state="visible", timeout=10000)
    btn.click()
    log("clicked 登录")
    page.wait_for_timeout(3000)
    log("after-login url =", page.url)
    page.screenshot(path=os.path.join(SHOT, "02_after_login.png"))

    # 走演示页：勾选「我已理解」-> 点「开始任务」-> 进入 /task
    if "/demo" not in page.url:
        page.goto(BASE + "/demo", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
    log("demo url =", page.url)
    page.screenshot(path=os.path.join(SHOT, "03_demo.png"))
    page.locator('input[type="checkbox"]').first.check()
    page.wait_for_timeout(500)
    page.get_by_role("button", name="开始任务").click()
    page.wait_for_url("**/task", timeout=15000)
    page.wait_for_timeout(2500)
    log("task url =", page.url)
    page.screenshot(path=os.path.join(SHOT, "04_task.png"))

    # 2) 展开讨论室
    expand = page.get_by_text("展开讨论室")
    expand.wait_for(state="visible", timeout=10000)
    expand.click()
    page.wait_for_timeout(1500)
    page.screenshot(path=os.path.join(SHOT, "04_expanded.png"))

    # 3) 发首条偏好，触发 SSE
    inp = page.get_by_placeholder(PREF_IDLE)
    inp.wait_for(state="visible", timeout=10000)
    inp.fill("一个人，3天，预算1000元，喜欢人文和美食，不要太赶")
    inp.press("Enter")
    log("sent initial preference (start SSE)")
    page.wait_for_timeout(2500)
    page.screenshot(path=os.path.join(SHOT, "05_after_start.png"))

    # 4) 等待专家发言出现
    saw_experts = False
    for _ in range(40):
        txt = page.inner_text("body")
        if any(n in txt for n in ["林小算", "苏格格", "老徐", "阿豪", "主持人"]):
            saw_experts = True
            break
        time.sleep(1)
    steps["experts_appeared"] = saw_experts
    page.screenshot(path=os.path.join(SHOT, "06_experts.png"))
    log("experts_appeared =", saw_experts)

    # 5) 轮询：反问 -> 回填；确认门 -> 确认；done -> 导出
    responded_user = False
    responded_confirm = False
    done = False
    for i in range(240):  # 最多 240s
        ph = chat_placeholder(page)
        # 反问等待（必须可编辑，验证 setLoading(false) 修复生效）
        if ph == PREF_USER and not responded_user:
            log(f">>> await_user detected (iter {i})")
            page.screenshot(path=os.path.join(SHOT, "07_await_user.png"))
            ui = page.get_by_placeholder(PREF_USER)
            ui.wait_for(state="visible", timeout=8000)
            steps["user_input_enabled"] = not ui.is_disabled()
            log("  await_user input disabled? ", ui.is_disabled(), "(期望 False=可编辑)")
            ui.fill("我喜欢安静一点的景点，预算控制在800元以内")
            ui.press("Enter")
            responded_user = True
            log("sent user answer")
            page.wait_for_timeout(2000)
            continue
        # 确认门等待（必须可编辑）
        if ph == PREF_CONFIRM and not responded_confirm:
            log(f">>> await_confirm detected (iter {i})")
            page.screenshot(path=os.path.join(SHOT, "08_await_confirm.png"))
            ci = page.get_by_placeholder(PREF_CONFIRM)
            ci.wait_for(state="visible", timeout=8000)
            steps["confirm_input_enabled"] = not ci.is_disabled()
            log("  await_confirm input disabled? ", ci.is_disabled(), "(期望 False=可编辑)")
            ci.fill("确认")
            ci.press("Enter")
            responded_confirm = True
            log("sent 确认")
            page.wait_for_timeout(2000)
            continue
        # 完成：placeholder 回到默认 + 已回答两轮 + 导出按钮可用
        if ph == PREF_IDLE and responded_user and responded_confirm:
            exp_btn = page.get_by_text("导出 Word")
            if exp_btn.count() > 0 and not exp_btn.first.is_disabled():
                done = True
                log(">>> done: 导出 Word 可用")
                break
        time.sleep(0.5)
    steps["responded_user"] = responded_user
    steps["responded_confirm"] = responded_confirm
    steps["done"] = done
    page.screenshot(path=os.path.join(SHOT, "09_final.png"))

    # 6) 点击导出（验证可点击、触发下载）
    try:
        exp_btn = page.get_by_text("导出 Word")
        if exp_btn.count() > 0 and not exp_btn.first.is_disabled():
            with page.expect_download(timeout=20000) as dl:
                exp_btn.first.click()
            download = dl.value
            steps["export_filename"] = download.suggested_filename
            log("export triggered, filename =", download.suggested_filename)
            steps["export_clicked"] = True
        else:
            steps["export_clicked"] = False
            log("export button not clickable (disabled or missing)")
    except Exception as e:
        log("export warn:", e)
        steps["export_clicked"] = False
    page.wait_for_timeout(1500)
    page.screenshot(path=os.path.join(SHOT, "10_after_export.png"))

    browser.close()

print("RESULTS:", steps)

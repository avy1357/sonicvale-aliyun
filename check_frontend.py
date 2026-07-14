from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    errors = []
    
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)
    
    page.goto("http://localhost:5173")
    page.wait_for_load_state("networkidle")
    
    screenshot_path = "d:/aliyun-sonicvale/frontend_check.png"
    page.screenshot(path=screenshot_path, full_page=True)
    
    title = page.title()
    
    nav_items = page.locator("nav a, .sidebar a, .el-menu-item").all()
    nav_text = [item.inner_text() for item in nav_items]
    
    console_errors = [e for e in errors if "error" in e.lower() or "warning" in e.lower()]
    
    result = {
        "page_title": title,
        "screenshot": screenshot_path,
        "navigation_items": nav_text[:15],
        "errors": console_errors[:20],
        "error_count": len(console_errors),
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    browser.close()

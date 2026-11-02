from _common import REPO, DEMO, DB_URL, API, DASH  # noqa: E402
import re, sys, json
from playwright.sync_api import sync_playwright, expect

D = DASH
# sample "after cleanup" photo (any valid image works; the demo AI stub counts 2 objects for /after/ files)
import random
from PIL import Image
_r = random.Random(77); _im = Image.new("RGB", (400, 300)); _im.putdata([(_r.randint(30, 220),) * 3 for _ in range(120000)]); _im.save(DEMO / "after.jpg")
results, errors = [], []

def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))

def login(page, email, pw):
    page.goto(f"{D}/login")
    page.fill("input[type=email]", email); page.fill("input[type=password]", pw)
    page.click("button[type=submit]")
    page.wait_for_url(re.compile(r"/$"), timeout=8000)

def logout(page):
    page.click("text=Log out"); page.wait_for_url(re.compile(r"/login"), timeout=5000)

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True)
    ctx.grant_permissions(["geolocation"]); ctx.set_geolocation({"latitude": 17.385, "longitude": 78.486})
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" and "403" not in m.text else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url}") if r.status >= 400 and "fonts.g" not in r.url and "tile.openstreetmap" not in r.url else None)

    # ---------- ADMIN ----------
    login(page, "admin@wastewatch.dev", "AdminPass123")
    page.wait_for_selector("text=Total Reports")
    check("admin dashboard cards", page.locator(".stat-card").count() >= 10, page.locator(".stat-card").count())
    check("cards show real total (6)", page.locator(".stat-card", has_text="Total Reports").locator(".value").inner_text() == "6")
    page.screenshot(path=str(DEMO / "s_admin_home.png"))

    page.goto(f"{D}/reports")
    try:
        expect(page.locator("table tbody tr")).to_have_count(6, timeout=6000); ok = True
    except AssertionError:
        ok = False
    check("reports list rows == 6", ok, page.locator("table tbody tr").count())
    page.fill("input[aria-label=Search]", "Tech") if page.locator("input[aria-label=Search]").count() else None
    page.goto(f"{D}/reports")
    page.select_option("select[aria-label='Assigned staff']", label="Demo Staff")
    try:
        expect(page.locator("table tbody tr")).to_have_count(1, timeout=5000); ok = True
    except AssertionError:
        ok = False
    check("filter by assigned staff -> only their task", ok, page.locator("table tbody tr").count())
    page.select_option("select[aria-label='Assigned staff']", label="Any staff")
    page.fill("input[aria-label='From date']", "2099-01-01")
    try:
        expect(page.locator("text=No reports match these filters")).to_have_count(1, timeout=5000); ok = True
    except AssertionError:
        ok = False
    check("future date range -> empty state", ok)
    page.fill("input[aria-label='From date']", "2000-01-01"); page.fill("input[aria-label='To date']", "2099-12-31")
    try:
        expect(page.locator("table tbody tr")).to_have_count(6, timeout=5000); ok = True
    except AssertionError:
        ok = False
    check("wide date range -> all 6 reports", ok)
    page.click("text=Clear filters")
    with page.expect_download(timeout=8000) as dl:
        page.click("text=Export CSV")
    check("CSV export downloads", dl.value.suggested_filename.endswith(".csv"))
    with page.expect_download(timeout=8000) as dl2:
        page.click("text=Export Excel")
    check("Excel export downloads", dl2.value.suggested_filename.endswith(".xlsx"))

    page.goto(f"{D}/reports/1"); page.wait_for_selector("text=AI detection")
    page.wait_for_selector("svg rect", timeout=8000)
    check("bounding boxes drawn on photo", page.locator("svg rect").count() >= 2, page.locator("svg rect").count())
    body = page.inner_text("body")
    check("report shows severity/priority/model/confidence", all(k in body for k in ("Severity", "Priority", "Model", "Detection Confidence")))
    check("hotspot link on clustered report", page.locator(".card a[href='/hotspots']").count() == 1)
    page.screenshot(path=str(DEMO / "s_report.png"), full_page=True)

    page.goto(f"{D}/reports/4"); page.wait_for_selector("text=Possible duplicate")
    try:
        expect(page.locator("button", has_text="Confirm duplicate")).to_have_count(1, timeout=5000); ok = True
    except AssertionError:
        ok = False
    check("duplicate panel with actions", ok)

    page.goto(f"{D}/hotspots"); page.wait_for_selector("text=Active and past hotspots")
    row_cells = [c.strip() for c in page.locator("table tbody tr", has_text="#1").first.inner_text().split("\t")]
    check("hotspot #1 lists 4 reports (3 piles + 1 flagged duplicate)", row_cells[:2] == ["#1", "4"], row_cells)
    page.locator("table tbody tr", has_text="#1").first.click()
    page.wait_for_selector("text=Hotspot #1 history")
    try:
        expect(page.locator("strong", has_text="New report")).to_have_count(4, timeout=5000); ok = True
    except AssertionError:
        ok = False
    check("hotspot timeline has 4 report events", ok, page.locator("strong", has_text="New report").count())
    check("hotspot map rendered", page.locator(".leaflet-container").count() >= 1)
    page.screenshot(path=str(DEMO / "s_hotspots.png"), full_page=True)

    page.goto(f"{D}/duplicates")
    try:
        expect(page.locator("table tbody tr", has_text="PENDING")).to_have_count(1, timeout=6000); ok = True
    except AssertionError:
        ok = False
    check("duplicate queue has exactly 1 pending (different photos 22 m apart NOT flagged)", ok, page.locator("table tbody tr", has_text="PENDING").count())
    page.click("button:has-text('Not duplicate')"); page.wait_for_selector("text=Nothing to review")
    check("dismissing duplicate empties queue", True)

    page.goto(f"{D}/map"); page.wait_for_selector(".leaflet-container")
    page.wait_for_timeout(1500)
    n_marks = page.locator(".marker-cluster, path.leaflet-interactive").count()
    check("map shows clustered/plotted reports", n_marks >= 1, n_marks)
    page.screenshot(path=str(DEMO / "s_map.png"))

    page.goto(f"{D}/analytics"); page.wait_for_selector(".recharts-wrapper", timeout=8000)
    page.wait_for_timeout(800)
    check("analytics charts render", page.locator(".recharts-wrapper").count() >= 6, page.locator(".recharts-wrapper").count())
    page.select_option("select[aria-label=Period]", "week"); page.wait_for_timeout(400)
    page.select_option("select[aria-label=Period]", "month"); page.wait_for_timeout(400)
    check("analytics period switch ok", page.locator(".recharts-wrapper").count() >= 6)
    page.screenshot(path=str(DEMO / "s_analytics.png"), full_page=True)

    page.goto(f"{D}/users"); page.wait_for_selector("text=Create staff or admin account")
    page.fill("#un", "Field Officer"); page.fill("#ue", "officer@wastewatch.dev"); page.fill("#up", "OfficerPass123")
    page.select_option("#ur", "STAFF"); page.click("button:has-text('Create account')")
    page.wait_for_selector("text=Account created for officer@wastewatch.dev")
    check("admin creates staff account in UI", page.locator("table tbody tr", has_text="officer@wastewatch.dev").count() == 1)

    page.goto(f"{D}/system"); page.wait_for_selector("text=AI models")
    try:
        expect(page.locator("text=No trained models registered yet")).to_have_count(1, timeout=5000); ok = True
    except AssertionError:
        ok = False
    check("system page: honest empty model list", ok)
    page.fill("#duplicate_distance_m", "60"); page.click("text=Save settings")
    page.wait_for_selector("text=Settings saved.")
    check("settings save", True)

    page.goto(f"{D}/reports/6"); page.wait_for_selector("text=Review")
    page.click("button:has-text('Verify (AI correct)')"); page.wait_for_selector("text=Report verified.")
    page.wait_for_selector("text=Assign cleanup")
    page.select_option("select[aria-label=Staff]", label="Demo Staff"); page.click("button:has-text('Assign')")
    page.wait_for_selector("text=Assigned.")
    check("admin verifies then assigns (workflow via UI)", page.locator("text=ASSIGNED").count() >= 1)

    page.goto(f"{D}/audit-log")
    try:
        for k in ("SETTING_CHANGED", "STATUS_VERIFIED", "USER_CREATED", "DUPLICATE_NOT_DUPLICATE"):
            expect(page.locator("table")).to_contain_text(k, timeout=5000)
        ok = True
    except AssertionError:
        ok = False
    check("audit log records actions with old/new", ok)
    logout(page)

    # ---------- STAFF ----------
    login(page, "staff@wastewatch.dev", "StaffPass123")
    page.wait_for_selector("text=My cleanup tasks")
    check("staff sees dedicated staff dashboard", page.locator("text=Staff dashboard").count() == 1)
    check("staff sidebar has no admin links", page.locator("nav a", has_text="Users").count() == 0 and page.locator("nav a", has_text="System").count() == 0)
    try:
        expect(page.locator(".card", has_text="My cleanup tasks").locator("tbody tr")).to_have_count(2, timeout=5000); ok = True
    except AssertionError:
        ok = False
    check("staff tasks list has 2 assigned", ok)
    page.click("text=Use my location"); page.wait_for_selector("text=Closest first", timeout=6000)
    check("nearby reports via browser GPS", page.locator(".card", has_text="Closest first").locator("tbody tr").count() >= 1)
    page.screenshot(path=str(DEMO / "s_staff_home.png"), full_page=True)
    page.goto(f"{D}/users"); page.wait_for_timeout(500)
    check("staff blocked from /users", "/users" not in page.url)

    page.goto(f"{D}/reports/5"); page.wait_for_selector("text=Cleanup task")
    page.click("button:has-text('Start cleanup')"); page.wait_for_selector("text=Cleanup started.")
    page.wait_for_selector("text=Complete cleanup")
    page.set_input_files("#af", str(DEMO / "after.jpg")); page.fill("#rm", "Cleared and swept")
    page.click("button:has-text('Complete cleanup')")
    page.wait_for_selector("text=Cleanup evidence", timeout=8000)
    ev = page.inner_text("body")
    check("cleanup evidence: before/after AI counts", "12 before" in ev and "2 after" in ev, ev[ev.find("AI count"):ev.find("AI count")+80])
    check("improvement percentage shown (83.3%)", "83.3%" in ev)
    check("status is CLEANUP VERIFICATION", "CLEANUP VERIFICATION" in ev)
    page.screenshot(path=str(DEMO / "s_cleanup.png"), full_page=True)
    check("assigned staff cannot approve own cleanup (UI hides it, shows note)", page.locator("button:has-text('Approve & close')").count() == 0 and page.locator("text=cannot sign off your own work").count() == 1)
    logout(page)

    # a DIFFERENT staff member (created earlier through the Users page) verifies
    login(page, "officer@wastewatch.dev", "OfficerPass123")
    page.wait_for_selector("text=Verification requests")
    try:
        expect(page.locator(".card", has_text="Verification requests").locator("tbody tr")).to_have_count(1, timeout=5000); ok = True
    except AssertionError:
        ok = False
    check("other staff sees the cleanup in their verification queue", ok)
    page.goto(f"{D}/reports/5"); page.wait_for_selector("text=Cleanup evidence")
    page.fill("input[aria-label='Verification remarks']", "Checked on site")
    page.click("button:has-text('Approve & close')"); page.wait_for_selector("text=Cleanup approved", timeout=8000)
    page.wait_for_timeout(600)
    check("other staff approves -> CLOSED", "CLOSED" in page.inner_text("body"))
    logout(page)

    # ---------- ADMIN final ----------
    login(page, "admin@wastewatch.dev", "AdminPass123")
    page.wait_for_selector("text=Completed Cleanups")
    check("completed cleanups card = 1", page.locator(".stat-card", has_text="Completed Cleanups").locator(".value").inner_text() == "1")
    check("avg resolution card populated", page.locator(".stat-card", has_text="Avg Resolution").locator(".value").inner_text() != "-")
    page.goto(f"{D}/analytics"); page.wait_for_selector("text=Cleanup completion")
    check("analytics: cleanup completion + improvement", "83.3%" in page.inner_text("body"))

    # mobile-size layout sanity
    page.set_viewport_size({"width": 390, "height": 800}); page.goto(f"{D}/reports"); page.wait_for_selector("table")
    overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2")
    page.screenshot(path=str(DEMO / "s_mobile_reports.png"))
    check("no page-level horizontal overflow at 390px", not overflow)
    b.close()

print("\nCONSOLE/NETWORK ERRORS:", len(errors))
for e in errors[:12]: print("  ", e[:200])
failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} UI checks passed")
sys.exit(1 if failed else 0)

from playwright.sync_api import sync_playwright

FRONTEND_URL = "http://localhost:5173"
XML_PATH = r"C:\Users\Oem\OneDrive\Desktop\saas-fiscal-demo\app\xmls_testes\xml_icms10_st_real.xml"

logs = []
ui_message = None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="msedge")
    page = browser.new_page()

    page.on("console", lambda msg: logs.append(msg.text))

    page.goto(FRONTEND_URL, wait_until="domcontentloaded")
    page.fill('input[placeholder="email"]', "demo@demo.com")
    page.fill('input[placeholder="senha"]', "qualquer")
    page.click('button[type="submit"]')

    page.wait_for_selector('input[type="file"]', timeout=15000)
    page.set_input_files('input[type="file"]', XML_PATH)
    page.wait_for_timeout(6000)

    job_line = next((line for line in logs if "JOB:" in line), None)
    if job_line:
        print(f"RESULT_JOB_LOG={job_line}")
    else:
        body_text = page.text_content("body") or ""
        candidates = [x.strip() for x in body_text.splitlines() if x.strip()]
        ui_message = next(
            (
                x
                for x in candidates
                if "erro" in x.lower() or "upload" in x.lower() or "xml" in x.lower()
            ),
            None,
        )
        if ui_message:
            print(f"RESULT_UI={ui_message}")
        else:
            print("RESULT_NONE=Sem JOB no console e sem mensagem visível clara.")

    browser.close()

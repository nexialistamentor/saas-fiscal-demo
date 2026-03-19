const { chromium } = require("playwright");

const FRONTEND_URL = "http://localhost:5173";
const XML_PATH = "C:/Users/Oem/OneDrive/Desktop/saas-fiscal-demo/app/xmls_testes/xml_icms10_st_real.xml";

(async () => {
  const tokenResp = await fetch("http://127.0.0.1:8000/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      username: "teste.swagger.local@demo.com",
      password: "123456"
    })
  });
  const tokenJson = await tokenResp.json();
  const accessToken = tokenJson.access_token;
  if (!accessToken) {
    throw new Error(`Falha ao obter token real: ${JSON.stringify(tokenJson)}`);
  }

  const logs = [];
  const browser = await chromium.launch({
    headless: true,
    channel: "msedge"
  });
  const page = await browser.newPage();
  page.on("console", (msg) => logs.push(msg.text()));

  await page.goto(FRONTEND_URL, { waitUntil: "domcontentloaded" });
  await page.fill('input[placeholder="email"]', "demo@demo.com");
  await page.fill('input[placeholder="senha"]', "qualquer");
  await page.click('button[type="submit"]');
  await page.waitForSelector('input[type="file"]', { timeout: 15000 });
  await page.evaluate((token) => {
    localStorage.setItem("auth_token", token);
  }, accessToken);
  await page.setInputFiles('input[type="file"]', XML_PATH);
  await page.waitForTimeout(7000);

  const jobLine = logs.find((line) => line.includes("JOB:"));
  if (jobLine) {
    console.log(`RESULT_JOB_LOG=${jobLine}`);
  } else {
    const bodyText = (await page.textContent("body")) || "";
    const uiMessage = bodyText
      .split(/\r?\n/)
      .map((x) => x.trim())
      .filter(Boolean)
      .find((x) => /erro|upload|xml/i.test(x));

    if (uiMessage) {
      console.log(`RESULT_UI=${uiMessage}`);
    } else {
      console.log("RESULT_NONE=Sem JOB no console e sem mensagem visível clara.");
    }
  }

  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});

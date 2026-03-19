const { chromium } = require("playwright");

const FRONTEND_URL = "http://127.0.0.1:5174";
const XML_PATH = "C:/Users/Oem/OneDrive/Desktop/saas-fiscal-demo/app/xmls_testes/xml_icms10_st_real.xml";
const LOGIN_EMAIL = "teste@teste.com";
const LOGIN_PASSWORD = "senha123";

(async () => {
  const tokenResp = await fetch("http://127.0.0.1:8000/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      username: LOGIN_EMAIL,
      password: LOGIN_PASSWORD,
    }),
  });
  const tokenJson = await tokenResp.json();
  const accessToken = tokenJson.access_token;
  if (!accessToken) {
    throw new Error(`Falha ao obter token: ${JSON.stringify(tokenJson)}`);
  }

  const logs = [];
  const browser = await chromium.launch({
    headless: true,
    channel: "msedge",
  });
  const page = await browser.newPage();
  page.on("console", (msg) => logs.push(msg.text()));

  await page.goto(FRONTEND_URL, { waitUntil: "domcontentloaded" });
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.fill('input[placeholder="email"]', "demo@demo.com");
  await page.fill('input[placeholder="senha"]', "qualquer");
  await page.click('button[type="submit"]');
  await page.waitForSelector('input[type="file"]', { timeout: 20000 });

  await page.evaluate((token) => {
    localStorage.setItem("auth_token", token);
  }, accessToken);
  await page.setInputFiles('input[type="file"]', XML_PATH);

  const timeoutMs = 90000;
  const start = Date.now();
  let finalLog = null;
  while (Date.now() - start < timeoutMs) {
    finalLog = logs.filter((line) => line.includes("JOB RESULTADO FINAL:")).pop() || null;
    if (finalLog) break;
    await page.waitForTimeout(1000);
  }

  if (!finalLog) {
    throw new Error(`Nao encontrou JOB RESULTADO FINAL em ${timeoutMs / 1000}s. Logs: ${JSON.stringify(logs.slice(-20))}`);
  }

  console.log(finalLog);
  await browser.close();
})().catch((err) => {
  console.error(err.stack || String(err));
  process.exit(1);
});

import { chromium } from "playwright";

const FRONTEND_URL = "http://localhost:5173";
const XML_PATH = "C:/Users/Oem/OneDrive/Desktop/saas-fiscal-demo/app/xmls_testes/xml_icms10_st_real.xml";

const logs = [];
let uiMessage = null;

const browser = await chromium.launch({
  headless: true,
  channel: "msedge"
});

const page = await browser.newPage();
page.on("console", (msg) => {
  logs.push(msg.text());
});

await page.goto(FRONTEND_URL, { waitUntil: "domcontentloaded" });

await page.fill('input[placeholder="email"]', "demo@demo.com");
await page.fill('input[placeholder="senha"]', "qualquer");
await page.click('button[type="submit"]');

await page.waitForSelector('input[type="file"]', { timeout: 15000 });
await page.setInputFiles('input[type="file"]', XML_PATH);

await page.waitForTimeout(5000);

const jobLine = logs.find((line) => line.includes("JOB:"));
if (jobLine) {
  console.log(`RESULT_JOB_LOG=${jobLine}`);
} else {
  const bodyText = await page.textContent("body");
  uiMessage = bodyText
    ?.split("\n")
    .map((x) => x.trim())
    .filter(Boolean)
    .find((x) => x.toLowerCase().includes("erro") || x.toLowerCase().includes("upload") || x.toLowerCase().includes("xml"));
  if (uiMessage) {
    console.log(`RESULT_UI=${uiMessage}`);
  } else {
    console.log("RESULT_NONE=Sem JOB no console e sem mensagem visível clara.");
  }
}

await browser.close();

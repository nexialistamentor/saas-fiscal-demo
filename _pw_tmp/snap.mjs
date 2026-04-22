import { chromium } from "playwright"

const browser = await chromium.launch()
const page = await browser.newPage()
await page.goto("http://127.0.0.1:5174/", { waitUntil: "networkidle" })
await page.getByRole("heading", { name: "Login" }).waitFor({ timeout: 60000 })
await page.getByRole("button", { name: "Criar conta" }).click()
await page.getByText("Mínimo de 8 caracteres.").waitFor({ state: "visible" })
await page.screenshot({
  path: "c:\\dev\\saas-fiscal-demo\\registo-hint-password.png",
  fullPage: true,
})
await browser.close()
console.log("screenshot ok")

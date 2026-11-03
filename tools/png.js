// Render generated/*.svg to PNG for sharing. Needs Playwright with Chromium:
//   node tools/png.js
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

(async () => {
  const dir = path.join(__dirname, "..", "generated");
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 2 });
  for (const f of fs.readdirSync(dir).filter((f) => f.endsWith(".svg"))) {
    const svg = fs.readFileSync(path.join(dir, f), "utf8");
    const [, w, h] = svg.match(/width="(\d+)" height="(\d+)"/);
    await page.setViewportSize({ width: +w, height: +h });
    await page.setContent(`<html><body style="margin:0">${svg}</body></html>`);
    const out = path.join(dir, f.replace(/\.svg$/, ".png"));
    await page.screenshot({ path: out, fullPage: true });
    console.log("wrote", path.relative(path.join(__dirname, ".."), out));
  }
  await browser.close();
})();

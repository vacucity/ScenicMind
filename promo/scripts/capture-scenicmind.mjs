import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(here, "../public/textures/live");
const layoutPath = path.resolve(here, "../src/aifl/live-layout.json");
const session = JSON.parse(fs.readFileSync(path.join(here, "demo-session.json"), "utf8"));
const edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";

fs.mkdirSync(outDir, { recursive: true });
const browser = await puppeteer.launch({ executablePath: edge, headless: true, args: ["--disable-gpu"] });
const page = await browser.newPage();
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 2 });

const settle = async (ms = 1300) => {
  await page.evaluate(() => document.fonts.ready);
  await new Promise((resolve) => setTimeout(resolve, ms));
};
const bbox = (handle) => handle.evaluate((node) => {
  const r = node.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height };
});
const screenshot = (name) => page.screenshot({ path: path.join(outDir, name), captureBeyondViewport: false });

await page.goto("http://127.0.0.1:5173/login", { waitUntil: "networkidle0" });
await page.evaluate((data) => {
  localStorage.setItem("scenicmind.accessToken", data.accessToken);
  localStorage.setItem("scenicmind.user", JSON.stringify(data.user));
  localStorage.setItem("scenicmind.activeAnalysisId", data.analysisId);
}, session);

// Public auth page, captured without any account data.
await page.evaluate(() => localStorage.clear());
await page.reload({ waitUntil: "networkidle0" });
await settle(500);
await screenshot("auth-full.png");

// Restore the isolated demo session and capture upload state.
await page.evaluate((data) => {
  localStorage.setItem("scenicmind.accessToken", data.accessToken);
  localStorage.setItem("scenicmind.user", JSON.stringify(data.user));
  localStorage.setItem("scenicmind.activeAnalysisId", data.analysisId);
}, session);
await page.goto("http://127.0.0.1:5173/upload", { waitUntil: "networkidle0" });
await settle();
await screenshot("upload-full.png");

// Main dashboard: true product screenshot + the ten real cards used by the deal shot.
await page.goto("http://127.0.0.1:5173/dashboard", { waitUntil: "networkidle0" });
await settle(1800);
await screenshot("projects-full.png");
await screenshot("detail-full.png");
const cardHandles = await page.$$(".snapshot-strip article, .week-day");
const cards = [];
for (let i = 0; i < Math.min(10, cardHandles.length); i += 1) {
  const file = `card${i + 1}.png`;
  const box = await bbox(cardHandles[i]);
  await cardHandles[i].screenshot({ path: path.join(outDir, file) });
  cards.push({ file, ...box, title: await cardHandles[i].evaluate((node) => node.textContent?.trim() || `metric-${i + 1}`) });
}
if (cardHandles[1]) await cardHandles[1].screenshot({ path: path.join(outDir, "card4-hires.png") });
const detailRows = [];
for (const item of await page.$$(".week-day")) detailRows.push(await bbox(item));
await page.evaluate(() => document.querySelectorAll(".snapshot-strip article, .week-day").forEach((node) => { node.style.visibility = "hidden"; }));
await screenshot("projects-empty.png");

// Capture the product's real 30-day state so the promo switch is truthful.
await page.reload({ waitUntil: "networkidle0" });
await settle(900);
await page.evaluate(() => [...document.querySelectorAll("button")].find((node) => node.textContent?.trim() === "30天")?.click());
await settle(1400);
await page.evaluate(() => document.querySelectorAll(".snapshot-strip article, .week-day").forEach((node) => { node.style.visibility = "hidden"; }));
await screenshot("projects-30d-empty.png");

// Indicator blueprint view and real module cutouts.
await page.reload({ waitUntil: "networkidle0" });
await settle(1200);
await page.evaluate(() => [...document.querySelectorAll("a")].find((node) => node.textContent?.includes("指标蓝图"))?.click());
await settle(700);
await screenshot("papers-full.png");
const paperHandles = await page.$$(".indicator-block");
const paperCards = [];
for (let i = 0; i < Math.min(5, paperHandles.length); i += 1) {
  const file = `paper${i + 1}.png`;
  const box = await bbox(paperHandles[i]);
  await paperHandles[i].screenshot({ path: path.join(outDir, file) });
  paperCards.push({ file, ...box });
}

// Explainability view stands in for the original collaborative brief scene.
await page.evaluate(() => [...document.querySelectorAll("a")].find((node) => node.textContent?.includes("经营分析"))?.click());
await settle(700);
await screenshot("wbr-full.png");
const blocks = [];
for (const item of await page.$$(".contribution-list li")) blocks.push({ ...(await bbox(item)), tag: "li" });

const layout = {
  pageW: 1920,
  projects: { pageH: 1080, cards },
  detail: { pageH: 1080, rows: detailRows },
  papers: { pageH: 1080, cards: paperCards },
  wbr: { pageH: 1080, blocks },
};
fs.writeFileSync(layoutPath, JSON.stringify(layout, null, 2), "utf8");
console.log(JSON.stringify({ cards: cards.length, papers: paperCards.length, blocks: blocks.length, layoutPath }));
await browser.close();

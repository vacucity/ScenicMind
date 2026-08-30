import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const API = "http://127.0.0.1:8000/api/v1";
const username = "scenicmind_demo";
const email = "demo@scenicmind.local";
// 密码通过环境变量注入，避免硬编码进仓库（勿将真实密钥写入源码）。
const password = process.env.DEMO_PASSWORD;
if (!password) {
  console.error("Missing DEMO_PASSWORD: set it to the demo account password before seeding.");
  process.exit(1);
}

const start = new Date("2026-03-03T00:00:00Z");
const rows = ["date,visitors,temperature,precipitation,known_reserved,search_index"];
for (let i = 0; i < 180; i += 1) {
  const date = new Date(start.getTime() + i * 86_400_000);
  const weekday = date.getUTCDay();
  const weekendLift = weekday === 0 || weekday === 6 ? 4200 : 0;
  const season = Math.round(3400 * Math.sin((i - 28) / 38));
  const festival = i >= 118 && i <= 122 ? 5800 : 0;
  const weatherPulse = (i * 17) % 23;
  const precipitation = weatherPulse < 4 ? (4 + weatherPulse * 2.4).toFixed(1) : "0.0";
  const rainPenalty = Number(precipitation) > 0 ? -2100 : 0;
  const temperature = (13 + i * 0.09 + 5 * Math.sin(i / 24)).toFixed(1);
  const visitors = Math.max(5200, 14200 + season + weekendLift + festival + rainPenalty + ((i * 137) % 1700));
  const reservations = Math.round(visitors * (0.54 + ((i % 9) / 100)));
  const searchIndex = Math.round(68 + visitors / 620 + ((i * 7) % 19));
  rows.push(`${date.toISOString().slice(0, 10)},${visitors},${temperature},${precipitation},${reservations},${searchIndex}`);
}

async function jsonRequest(url, init) {
  const response = await fetch(url, init);
  const body = await response.json().catch(() => ({}));
  return { response, body };
}

let auth = await jsonRequest(`${API}/auth/register`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username, email, password }),
});
if (!auth.response.ok) {
  auth = await jsonRequest(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}
if (!auth.response.ok) throw new Error(`Auth failed: ${JSON.stringify(auth.body)}`);

const here = path.dirname(fileURLToPath(import.meta.url));
const csvPath = path.join(here, "scenicmind-demo.csv");
fs.writeFileSync(csvPath, `${rows.join("\n")}\n`, "utf8");

const form = new FormData();
form.append("file", new Blob([rows.join("\n")], { type: "text/csv" }), "scenicmind-demo.csv");
const upload = await jsonRequest(`${API}/analyses`, {
  method: "POST",
  headers: { Authorization: `Bearer ${auth.body.accessToken}` },
  body: form,
});
if (!upload.response.ok) throw new Error(`Upload failed: ${JSON.stringify(upload.body)}`);

fs.writeFileSync(
  path.join(here, "demo-session.json"),
  JSON.stringify({ accessToken: auth.body.accessToken, user: auth.body.user, analysisId: upload.body.analysisId }, null, 2),
  "utf8",
);
console.log(JSON.stringify({ csvPath, analysisId: upload.body.analysisId, status: upload.body.status }));

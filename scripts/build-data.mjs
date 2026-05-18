/** Copy CSV data to public/data/*.json for static + API use on Vercel */
import { readFileSync, mkdirSync, writeFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "AI_Interview_Preparation_Assistant", "data");
const dest = join(root, "public", "data");

// Verify source files exist
if (!existsSync(join(src, "questions.csv"))) {
  console.error(`ERROR: questions.csv not found at ${join(src, "questions.csv")}`);
  process.exit(1);
}
if (!existsSync(join(src, "expenses.csv"))) {
  console.error(`ERROR: expenses.csv not found at ${join(src, "expenses.csv")}`);
  process.exit(1);
}

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const headers = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const values = [];
    let cur = "";
    let inQuotes = false;
    for (const ch of line) {
      if (ch === '"') {
        inQuotes = !inQuotes;
        continue;
      }
      if (ch === "," && !inQuotes) {
        values.push(cur);
        cur = "";
        continue;
      }
      cur += ch;
    }
    values.push(cur);
    const row = {};
    headers.forEach((h, i) => {
      row[h.trim()] = (values[i] || "").trim();
    });
    if (row.amount) row.amount = parseFloat(row.amount);
    if (row.id) row.id = parseInt(row.id, 10);
    return row;
  });
}

try {
  mkdirSync(dest, { recursive: true });

  for (const name of ["questions", "expenses"]) {
    const csv = readFileSync(join(src, `${name}.csv`), "utf8");
    writeFileSync(join(dest, `${name}.json`), JSON.stringify(parseCsv(csv), null, 2));
  }

  writeFileSync(
    join(dest, "users.json"),
    JSON.stringify(
      { demo: { password: "demo123" }, admin: { password: "admin123" } },
      null,
      2
    )
  );

  console.log("✓ Built public/data/*.json for Vercel");
  process.exit(0);
} catch (error) {
  console.error("Build failed:", error.message);
  console.error(error);
  process.exit(1);
}

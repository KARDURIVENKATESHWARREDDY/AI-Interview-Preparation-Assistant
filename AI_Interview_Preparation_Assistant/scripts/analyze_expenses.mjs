/**
 * Expense analysis using @google/genai JavaScript SDK.
 * Usage: echo '{"username":"demo","expenses":[...]}' | node scripts/analyze_expenses.mjs
 */
import { GoogleGenAI } from "@google/genai";
import { readFileSync } from "fs";

const MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"];

function getApiKey() {
  return process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY || "";
}

function buildPrompt(username, expenses) {
  const lines = expenses.map(
    (e) =>
      `- ${e.expense_date}: ${e.title} | $${Number(e.amount).toFixed(2)} | ${e.category} | ${e.notes || ""}`
  );
  const total = expenses.reduce((s, e) => s + Number(e.amount), 0);
  return `You are a personal finance assistant. Analyze expenses for user "${username}".

Total: $${total.toFixed(2)} across ${expenses.length} expenses.

Detailed list:
${lines.length ? lines.join("\n") : "No expenses yet."}

Provide a concise report with:
1. Top spending categories
2. One savings tip
3. Any unusual patterns
Keep under 200 words. Use bullet points.`;
}

async function main() {
  const apiKey = getApiKey();
  if (!apiKey) {
    console.log(
      JSON.stringify({
        ok: false,
        error:
          "Set GOOGLE_API_KEY or GEMINI_API_KEY for the @google/genai SDK.",
      })
    );
    process.exit(0);
  }

  let payload;
  try {
    const raw = readFileSync(0, "utf8");
    payload = JSON.parse(raw);
  } catch (e) {
    console.log(JSON.stringify({ ok: false, error: `Invalid input: ${e.message}` }));
    process.exit(0);
  }

  const { username = "user", expenses = [] } = payload;
  const ai = new GoogleGenAI({ apiKey });
  const prompt = buildPrompt(username, expenses);

  let lastError = null;
  for (const model of MODELS) {
    try {
      const response = await ai.models.generateContent({
        model,
        contents: prompt,
      });
      const text = response.text ?? String(response);
      console.log(JSON.stringify({ ok: true, text: text.trim(), model }));
      return;
    } catch (e) {
      lastError = e;
    }
  }

  console.log(
    JSON.stringify({
      ok: false,
      error: `Gemini SDK error: ${lastError?.message || lastError}`,
    })
  );
}

main();

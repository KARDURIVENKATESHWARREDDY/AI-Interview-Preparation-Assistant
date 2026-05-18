import { GoogleGenAI } from "@google/genai";

const MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"];

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }
  if (req.method !== "POST") {
    return res.status(405).json({ ok: false, error: "Method not allowed" });
  }

  const apiKey = process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return res.status(500).json({
      ok: false,
      error: "Set GOOGLE_API_KEY in Vercel project Environment Variables.",
    });
  }

  const { username = "user", expenses = [] } = req.body || {};
  const lines = expenses.map(
    (e) =>
      `- ${e.expense_date}: ${e.title} | $${Number(e.amount).toFixed(2)} | ${e.category}`
  );
  const total = expenses.reduce((s, e) => s + Number(e.amount || 0), 0);
  const prompt = `Analyze expenses for "${username}". Total: $${total.toFixed(2)}.

${lines.join("\n") || "No expenses."}

Give: top categories, one savings tip, unusual patterns. Under 200 words, bullet points.`;

  const ai = new GoogleGenAI({ apiKey });
  let lastError = null;

  for (const model of MODELS) {
    try {
      const response = await ai.models.generateContent({ model, contents: prompt });
      const text = response.text ?? String(response);
      return res.status(200).json({ ok: true, text: text.trim(), model });
    } catch (e) {
      lastError = e;
    }
  }

  return res.status(500).json({
    ok: false,
    error: `Gemini SDK error: ${lastError?.message || lastError}`,
  });
}

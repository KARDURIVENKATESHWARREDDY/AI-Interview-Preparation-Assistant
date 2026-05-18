import { GoogleGenAI } from "@google/genai";

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") {
    return res.status(405).json({ ok: false, error: "Method not allowed" });
  }

  const apiKey = process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY;
  const { question, answer, category = "" } = req.body || {};

  if (!question || !answer?.trim()) {
    return res.status(400).json({ ok: false, error: "Question and answer required." });
  }

  if (!apiKey) {
    return res.status(200).json({
      ok: true,
      text: _offlineFeedback(answer),
      offline: true,
    });
  }

  const prompt = `You are an interview coach. Question (${category}): ${question}

Candidate answer:
${answer}

Give: score /100, 2 strengths, 2 improvements, brief summary. Bullet points.`;

  const ai = new GoogleGenAI({ apiKey });
  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.0-flash",
      contents: prompt,
    });
    return res.status(200).json({
      ok: true,
      text: (response.text ?? String(response)).trim(),
    });
  } catch (e) {
    return res.status(200).json({
      ok: true,
      text: _offlineFeedback(answer),
      offline: true,
      error: e.message,
    });
  }
}

function _offlineFeedback(answer) {
  const words = answer.trim().split(/\s+/).length;
  let score = Math.min(100, 30 + words);
  if (/\d+/.test(answer)) score += 15;
  if (/I |my |we /i.test(answer)) score += 10;
  return `**Score: ${score}/100** (offline mode)\n\n- Add specific examples and metrics.\n- Use STAR for behavioral questions.\n- Keep answers 4–6 sentences.`;
}

export default function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.status(200).json({
    ok: true,
    service: "AI Interview Preparation Assistant",
    platform: "vercel",
  });
}

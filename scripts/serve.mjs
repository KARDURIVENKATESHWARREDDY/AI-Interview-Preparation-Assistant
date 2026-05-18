/** Simple HTTP server to serve public directory on Render */
import http from "http";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.join(__dirname, "..", "public");
const PORT = process.env.PORT || 3000;

// MIME types
const mimeTypes = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
};

const server = http.createServer((req, res) => {
  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.writeHead(200).end();
  }

  // Route API requests (would be handled by Render's serverless functions)
  if (req.url.startsWith("/api/")) {
    res.writeHead(404, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ error: "API routes not available in static server" }));
  }

  // Serve static files
  let filePath = path.join(publicDir, req.url === "/" ? "index.html" : req.url);

  // Prevent directory traversal
  if (!filePath.startsWith(publicDir)) {
    res.writeHead(403, { "Content-Type": "text/plain" });
    return res.end("Forbidden");
  }

  // Try to serve the file
  fs.readFile(filePath, (err, content) => {
    if (err) {
      // If file not found, serve index.html for SPA routing
      if (err.code === "ENOENT") {
        fs.readFile(path.join(publicDir, "index.html"), (err2, content2) => {
          if (err2) {
            res.writeHead(404, { "Content-Type": "text/plain" });
            return res.end("404 Not Found");
          }
          res.writeHead(200, { "Content-Type": "text/html" });
          return res.end(content2);
        });
      } else {
        res.writeHead(500, { "Content-Type": "text/plain" });
        return res.end("500 Server Error");
      }
    } else {
      const ext = path.extname(filePath).toLowerCase();
      const contentType = mimeTypes[ext] || "application/octet-stream";
      res.writeHead(200, { "Content-Type": contentType });
      return res.end(content);
    }
  });
});

server.listen(PORT, () => {
  console.log(`✓ Server running on http://localhost:${PORT}`);
  console.log(`✓ Serving static files from ${publicDir}`);
});

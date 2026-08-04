import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "url";
import path from "path";
import { spawn } from "child_process";
import { stat } from "fs/promises";
import fs from "fs";
import http from "http";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");

function buildJsonResponse(res, payload, status = 200) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(payload));
}

function quoteShellPath(value) {
  return `"${String(value).replace(/"/g, '\\"')}"`;
}

function normalizeCommand(command) {
  const venvPython = path.resolve(projectRoot, "venv", "Scripts", "python.exe");
  if (process.platform !== "win32") return command;
  if (/^\s*pytest(\s|$)/i.test(command)) {
    return command.replace(/^\s*pytest/i, `& ${quoteShellPath(venvPython)} -m pytest`);
  }
  if (/^\s*python(\s|$)/i.test(command)) {
    return command.replace(/^\s*python/i, `& ${quoteShellPath(venvPython)}`);
  }
  return command;
}

// Separate Vite app for the testing dashboard. It runs on port 5174
// (the recruiter app stays on 5173) and has no shared bundle with it.
export default defineConfig({
  base: '/testing/',
  server: {
    host: true,
    port: 5174,
    strictPort: true,
    hmr: false,
    allowedHosts: [
      "host.docker.internal",
      "localhost",
      "127.0.0.1",
    ],
  },
  plugins: [
    react(),
    {
      name: "testing-dashboard-runtime",
      configureServer(server) {
        server.middlewares.use("/api/reports", (req, res, next) => {
          if (req.method !== "POST") return next();
          let body = "";
          req.on("data", (chunk) => { body += chunk; });
          req.on("end", async () => {
            try {
              const reports = JSON.parse(body || "[]");
              if (!Array.isArray(reports)) {
                return buildJsonResponse(res, { error: "Expected an array of reports." }, 400);
              }
              const rows = await Promise.all(reports.map(async (report) => {
                const relativePath = report && report.path ? report.path : "";
                const targetPath = path.isAbsolute(relativePath)
                  ? relativePath
                  : path.resolve(projectRoot, relativePath);
                if (!targetPath.startsWith(projectRoot)) {
                  return { ...report, exists: false, error: "Access denied" };
                }
                try {
                  const info = await stat(targetPath);
                  let exists = info.isFile();
                  let size = info.size;
                  let mtime = info.mtime.toISOString();
                  let finalPath = relativePath;

                  if (info.isDirectory() && report.filename && report.filename.includes("*")) {
                    const fs = await import("fs");
                    if (fs.existsSync(targetPath)) {
                      const files = fs.readdirSync(targetPath);
                      const regex = new RegExp("^" + report.filename.replace(/\*/g, ".*") + "$");
                      const matchingFiles = files
                        .filter(f => regex.test(f))
                        .map(f => {
                          const filePath = path.resolve(targetPath, f);
                          const fileStat = fs.statSync(filePath);
                          return {
                            name: f,
                            path: path.join(relativePath, f),
                            size: fileStat.size,
                            mtime: fileStat.mtime
                          };
                        })
                        .sort((a, b) => b.mtime - a.mtime); // latest first

                      if (matchingFiles.length > 0) {
                        exists = true;
                        size = matchingFiles[0].size;
                        mtime = matchingFiles[0].mtime.toISOString();
                        finalPath = matchingFiles[0].path;
                      }
                    }
                  }

                  return {
                    ...report,
                    exists,
                    size,
                    mtime,
                    path: finalPath,
                  };
                } catch (error) {
                  return { ...report, exists: false, path: relativePath };
                }
              }));
              return buildJsonResponse(res, rows);
            } catch (error) {
              return buildJsonResponse(res, { error: error.message }, 400);
            }
          });
        });

        // Secure report serving with appropriate MIME types
        server.middlewares.use("/api/reports/view", async (req, res, next) => {
          const urlObj = new URL(req.url, "http://localhost");
          const relativePath = urlObj.searchParams.get("path");
          if (!relativePath) {
            res.statusCode = 400;
            return res.end("Missing path parameter");
          }
          const targetPath = path.isAbsolute(relativePath)
            ? relativePath
            : path.resolve(projectRoot, relativePath);
          
          // Security sandbox check: prevent directory traversal
          if (!targetPath.startsWith(projectRoot)) {
            res.statusCode = 403;
            return res.end("Access denied");
          }

          try {
            const info = await stat(targetPath);
            if (!info.isFile()) {
              res.statusCode = 404;
              return res.end("Not a file");
            }
            
            let mimeType = "text/plain";
            const ext = path.extname(targetPath).toLowerCase();
            if (ext === ".html" || ext === ".htm") mimeType = "text/html";
            else if (ext === ".json") mimeType = "application/json";
            else if (ext === ".xml") mimeType = "application/xml";
            else if (ext === ".md") mimeType = "text/markdown";
            else if (ext === ".txt" || ext === ".log") mimeType = "text/plain";

            res.statusCode = 200;
            res.setHeader("Content-Type", mimeType);
            
            const download = urlObj.searchParams.get("download");
            if (download) {
              res.setHeader("Content-Disposition", `attachment; filename="${path.basename(targetPath)}"`);
            }

            const { createReadStream } = await import("fs");
            createReadStream(targetPath).pipe(res);
          } catch (e) {
            res.statusCode = 404;
            res.end("File not found");
          }
        });

        // Static directory server for multi-file HTML reports (e.g. htmlcov which needs CSS/JS/PNG assets).
        // Usage: /reports-static/<repo-relative-path>  e.g. /reports-static/reports/ci/backend-python-reports/htmlcov-python/index.html
        server.middlewares.use("/reports-static", async (req, res, next) => {
          const rawSubPath = decodeURIComponent(req.url || "/").replace(/^\/*/, "");
          if (!rawSubPath) { res.statusCode = 400; return res.end("Missing path"); }

          // Security sandbox check: prevent directory traversal
          const targetPath = path.resolve(projectRoot, rawSubPath);
          if (!targetPath.startsWith(projectRoot)) {
            res.statusCode = 403;
            return res.end("Access denied");
          }

          try {
            const info = await stat(targetPath);
            if (!info.isFile()) { res.statusCode = 404; return res.end("Not a file"); }

            const ext = path.extname(targetPath).toLowerCase();
            const mimeMap = {
              ".html": "text/html",
              ".htm":  "text/html",
              ".css":  "text/css",
              ".js":   "application/javascript",
              ".json": "application/json",
              ".xml":  "application/xml",
              ".txt":  "text/plain",
              ".log":  "text/plain",
              ".md":   "text/markdown",
              ".png":  "image/png",
              ".jpg":  "image/jpeg",
              ".jpeg": "image/jpeg",
              ".svg":  "image/svg+xml",
              ".gif":  "image/gif",
              ".ico":  "image/x-icon",
            };
            res.statusCode = 200;
            res.setHeader("Content-Type", mimeMap[ext] || "application/octet-stream");
            const { createReadStream } = await import("fs");
            createReadStream(targetPath).pipe(res);
          } catch (e) {
            res.statusCode = 404;
            res.end("File not found");
          }
        });

        // 2. Execute Command with virtual environment PATH & Live Log Streaming (SSE)
        server.middlewares.use("/api/execute", (req, res, next) => {
          if (req.method !== "POST") return next();
          let body = "";
          req.on("data", (chunk) => { body += chunk; });
          req.on("end", () => {
            try {
              const { cwd, command } = JSON.parse(body || "{}");
              const resolvedCwd = cwd && path.isAbsolute(cwd) ? cwd : path.resolve(projectRoot, cwd || ".");
              const normalizedCommand = normalizeCommand(command || "");
              
              if (command && command.includes("security-review")) {
                res.writeHead(200, {
                  "Content-Type": "text/event-stream",
                  "Cache-Control": "no-cache",
                  "Connection": "keep-alive",
                });

                res.write(`data: ${JSON.stringify({ type: "stdout", text: "Starting API-driven Security Review...\n" })}\n\n`);
                res.write(`data: ${JSON.stringify({ type: "stdout", text: "Reading code files...\n" })}\n\n`);

                let codeToReview;
                try {
                  codeToReview = fs.readFileSync(path.resolve(projectRoot, "api.py"), "utf8");
                } catch (e) {
                  res.write(`data: ${JSON.stringify({ type: "stderr", text: `Could not read api.py: ${e.message}\n` })}\n\n`);
                  res.write(`data: ${JSON.stringify({ type: "close", code: 1 })}\n\n`);
                  res.end();
                  return;
                }

                res.write(`data: ${JSON.stringify({ type: "stdout", text: "Calling FastAPI /api/review endpoint (this may take ~30s)...\n" })}\n\n`);

                const postData = JSON.stringify({
                  code: codeToReview,
                  provider: "Gemini",
                  model_name: "gemini-2.5-flash"
                });

                const apiReq = http.request({
                  hostname: "localhost",
                  port: 8000,
                  path: "/api/review",
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                    "Content-Length": Buffer.byteLength(postData)
                  }
                }, (apiRes) => {
                  let resBody = "";
                  apiRes.on("data", (chunk) => { resBody += chunk; });
                  apiRes.on("end", () => {
                    res.write(`data: ${JSON.stringify({ type: "stdout", text: `FastAPI responded with status: ${apiRes.statusCode}\n` })}\n\n`);
                    try {
                      if (apiRes.statusCode !== 200) {
                        res.write(`data: ${JSON.stringify({ type: "stderr", text: `Error from FastAPI: ${resBody}\n` })}\n\n`);
                        res.write(`data: ${JSON.stringify({ type: "close", code: 1 })}\n\n`);
                        res.end();
                        return;
                      }
                      const data = JSON.parse(resBody);
                      const reviewText = data.review || "No review content returned.";
                      res.write(`data: ${JSON.stringify({ type: "stdout", text: "Generating Security Review Report...\n" })}\n\n`);

                      const today = new Date().toISOString().split("T")[0];
                      const reportFilename = `security-review-all-${today}.html`;
                      const reportsDir = path.resolve(projectRoot, "skills", "reports");
                      if (!fs.existsSync(reportsDir)) fs.mkdirSync(reportsDir, { recursive: true });

                      const templatePath = path.resolve(reportsDir, "_template.html");
                      const escapedReview = reviewText
                        .replace(/&/g, "&amp;")
                        .replace(/</g, "&lt;")
                        .replace(/>/g, "&gt;");
                      let htmlContent = "";
                      if (fs.existsSync(templatePath)) {
                        const template = fs.readFileSync(templatePath, "utf8");
                        htmlContent = template
                          .replace(/__MODE__/g, "all")
                          .replace(/__DATE__/g, today)
                          .replace(/__TIMESTAMP__/g, new Date().toLocaleString())
                          .replace(/__SCOPE__/g, "api.py")
                          .replace(/__PASS_COUNT__/g, "0")
                          .replace(/__FAIL_COUNT__/g, "0")
                          .replace(/__WARNING_COUNT__/g, "1")
                          .replace(/__FINDINGS__/g, `<tr><td colspan="13"><pre style="white-space:pre-wrap;font-family:monospace;font-size:13px;color:#1e293b;padding:12px;background:#f8fafc;">${escapedReview}</pre></td></tr>`);
                      } else {
                        htmlContent = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Security Review ${today}</title><style>body{font-family:sans-serif;padding:24px;} pre{white-space:pre-wrap;background:#f8fafc;border:1px solid #e2e8f0;padding:16px;border-radius:6px;}</style></head><body><h1>Security Review &mdash; ${today}</h1><pre>${escapedReview}</pre></body></html>`;
                      }

                      fs.writeFileSync(path.resolve(reportsDir, reportFilename), htmlContent);
                      res.write(`data: ${JSON.stringify({ type: "stdout", text: `Report saved to skills/reports/${reportFilename}\n` })}\n\n`);
                      res.write(`data: ${JSON.stringify({ type: "close", code: 0 })}\n\n`);
                      res.end();
                    } catch (err) {
                      res.write(`data: ${JSON.stringify({ type: "stderr", text: `Error processing review response: ${err.message}\n` })}\n\n`);
                      res.write(`data: ${JSON.stringify({ type: "close", code: 1 })}\n\n`);
                      res.end();
                    }
                  });
                });

                apiReq.on("error", (err) => {
                  res.write(`data: ${JSON.stringify({ type: "stderr", text: `Cannot reach FastAPI on port 8000: ${err.message}\nMake sure the FastAPI server is running (start-app.ps1).\n` })}\n\n`);
                  res.write(`data: ${JSON.stringify({ type: "close", code: 1 })}\n\n`);
                  res.end();
                });

                apiReq.write(postData);
                apiReq.end();
                return;
              }

              // Code-review: read invoke.txt → Gemini /api/review → render checklist-report.html
              if (command && command.includes("code-review") && !command.includes("render_checklist")) {
                res.writeHead(200, {
                  "Content-Type": "text/event-stream",
                  "Cache-Control": "no-cache",
                  "Connection": "keep-alive",
                });

                res.write(`data: ${JSON.stringify({ type: "stdout", text: "Starting Code Review via Gemini...\n" })}\n\n`);

                const invokePath = path.resolve(projectRoot, ".code-review", "invoke.txt");
                let invokeContent;
                try {
                  invokeContent = fs.readFileSync(invokePath, "utf8");
                  res.write(`data: ${JSON.stringify({ type: "stdout", text: `Read invoke.txt (${invokeContent.length} chars)\n` })}\n\n`);
                } catch (e) {
                  res.write(`data: ${JSON.stringify({ type: "stderr", text: `Could not read .code-review/invoke.txt: ${e.message}\n` })}\n\n`);
                  res.write(`data: ${JSON.stringify({ type: "close", code: 1 })}\n\n`);
                  res.end();
                  return;
                }

                res.write(`data: ${JSON.stringify({ type: "stdout", text: "Sending invoke.txt to Gemini (this may take ~30-60s)...\n" })}\n\n`);

                const crPostData = JSON.stringify({
                  code: invokeContent,
                  provider: "Gemini",
                  model_name: "gemini-2.5-flash"
                });

                const crReq = http.request({
                  hostname: "localhost",
                  port: 8000,
                  path: "/api/review",
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                    "Content-Length": Buffer.byteLength(crPostData)
                  }
                }, (crRes) => {
                  let crBody = "";
                  crRes.on("data", (chunk) => { crBody += chunk; });
                  crRes.on("end", () => {
                    res.write(`data: ${JSON.stringify({ type: "stdout", text: `Gemini responded (status ${crRes.statusCode})\n` })}\n\n`);
                    try {
                      if (crRes.statusCode !== 200) {
                        res.write(`data: ${JSON.stringify({ type: "stderr", text: `FastAPI error: ${crBody}\n` })}\n\n`);
                        res.write(`data: ${JSON.stringify({ type: "close", code: 1 })}\n\n`);
                        res.end();
                        return;
                      }
                      const crData = JSON.parse(crBody);
                      const reviewMarkdown = crData.review || "No review returned.";
                      res.write(`data: ${JSON.stringify({ type: "stdout", text: "Generating checklist-report.html...\n" })}\n\n`);

                      const today = new Date().toISOString().split("T")[0];
                      const escapedMd = reviewMarkdown
                        .replace(/&/g, "&amp;")
                        .replace(/</g, "&lt;")
                        .replace(/>/g, "&gt;");
                      const reportHtml = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Code Review Report &mdash; ${today}</title>
<style>
  :root{--pass:#16a34a;--fail:#dc2626;--warn:#d97706;--border:#e5e7eb;}
  *{box-sizing:border-box;}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;padding:32px;color:#1a1a1a;line-height:1.6;}
  h1{font-size:24px;margin:0 0 4px 0;}
  .meta{color:#6b7280;font-size:13px;margin-bottom:24px;}
  .review-body{background:#f8fafc;border:1px solid var(--border);border-radius:8px;padding:24px;font-family:monospace;font-size:13px;white-space:pre-wrap;word-break:break-word;line-height:1.7;}
</style>
</head>
<body>
<h1>Code Review Report</h1>
<div class="meta">Generated: ${new Date().toLocaleString()} &nbsp;|&nbsp; Source: .code-review/invoke.txt</div>
<div class="review-body">${escapedMd}</div>
</body>
</html>`;

                      const outputPath = path.resolve(projectRoot, ".code-review", "checklist-report.html");
                      fs.mkdirSync(path.dirname(outputPath), { recursive: true });
                      fs.writeFileSync(outputPath, reportHtml, "utf8");

                      res.write(`data: ${JSON.stringify({ type: "stdout", text: `Report saved to .code-review/checklist-report.html\n` })}\n\n`);
                      res.write(`data: ${JSON.stringify({ type: "close", code: 0 })}\n\n`);
                      res.end();
                    } catch (err) {
                      res.write(`data: ${JSON.stringify({ type: "stderr", text: `Error generating report: ${err.message}\n` })}\n\n`);
                      res.write(`data: ${JSON.stringify({ type: "close", code: 1 })}\n\n`);
                      res.end();
                    }
                  });
                });

                crReq.on("error", (err) => {
                  res.write(`data: ${JSON.stringify({ type: "stderr", text: `Cannot reach FastAPI on port 8000: ${err.message}\nMake sure the FastAPI server is running.\n` })}\n\n`);
                  res.write(`data: ${JSON.stringify({ type: "close", code: 1 })}\n\n`);
                  res.end();
                });

                crReq.write(crPostData);
                crReq.end();
                return;
              }

              if (command.includes("render_checklist.py")) {
                const pythonExe = process.platform === "win32" ? "python.exe" : "python";
                const scriptPath = path.resolve(projectRoot, "skills", "code-review-policy", "render_checklist.py");
                const args = [
                  scriptPath,
                  "--structured", path.resolve(projectRoot, "skills", "code-review-policy", "templates", "checklist-structured.md"),
                  "--detailed", path.resolve(projectRoot, "skills", "code-review-policy", "templates", "checklist-detailed.md"),
                  "--data", path.resolve(projectRoot, ".code-review", "last-checklist-data.json"),
                  "--output", path.resolve(projectRoot, ".code-review", "checklist-report.html")
                ];

                res.writeHead(200, {
                  "Content-Type": "text/event-stream",
                  "Cache-Control": "no-cache",
                  "Connection": "keep-alive",
                });
                res.write(`data: ${JSON.stringify({ type: "stdout", text: `Running checklist generator...\n` })}\n\n`);

                const child = spawn(pythonExe, args, { cwd: projectRoot });
                child.stdout.on("data", (chunk) => {
                  res.write(`data: ${JSON.stringify({ type: "stdout", text: chunk.toString() })}\n\n`);
                });
                child.stderr.on("data", (chunk) => {
                  res.write(`data: ${JSON.stringify({ type: "stderr", text: chunk.toString() })}\n\n`);
                });
                child.on("close", (code) => {
                  res.write(`data: ${JSON.stringify({ type: "close", code })}\n\n`);
                  res.end();
                });
                child.on("error", (err) => {
                  res.write(`data: ${JSON.stringify({ type: "error", message: err.message })}\n\n`);
                  res.end();
                });
                return;
              }

              res.writeHead(200, {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
              });

              const shell = process.platform === "win32" ? "powershell.exe" : "/bin/bash";
              const args = process.platform === "win32"
                ? ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", normalizedCommand]
                : ["-lc", normalizedCommand];
                
              const env = { ...process.env, FORCE_COLOR: "0" };
              const venvBin = process.platform === "win32"
                ? path.resolve(projectRoot, "venv", "Scripts")
                : path.resolve(projectRoot, "venv", "bin");
              
              if (process.platform === "win32") {
                env.Path = `${venvBin};${env.Path || env.PATH || ""}`;
              } else {
                env.PATH = `${venvBin}:${env.PATH || ""}`;
              }

              const child = spawn(shell, args, { cwd: resolvedCwd, env });

              child.stdout.on("data", (chunk) => {
                res.write(`data: ${JSON.stringify({ type: "stdout", text: chunk.toString() })}\n\n`);
              });

              child.stderr.on("data", (chunk) => {
                res.write(`data: ${JSON.stringify({ type: "stderr", text: chunk.toString() })}\n\n`);
              });

              child.on("close", (code) => {
                res.write(`data: ${JSON.stringify({ type: "close", code })}\n\n`);
                res.end();
              });
              
              child.on("error", (err) => {
                res.write(`data: ${JSON.stringify({ type: "error", message: err.message })}\n\n`);
                res.end();
              });
            } catch (error) {
              res.statusCode = 400;
              res.end(JSON.stringify({ error: error.message }));
            }
          });
        });
      },
    },
  ],
});

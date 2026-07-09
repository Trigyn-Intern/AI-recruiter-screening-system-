import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "url";
import path from "path";
import { spawn } from "child_process";
import { stat } from "fs/promises";

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
  server: {
    host: true,
    port: 5174,
    strictPort: true,
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
                  return {
                    ...report,
                    exists: info.isFile(),
                    size: info.size,
                    mtime: info.mtime.toISOString(),
                    path: relativePath,
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

require("dotenv").config();

const crypto = require("crypto");
const express = require("express");
const cors = require("cors");

// Ensure JWT_SECRET is set before any module that calls jwt.sign() is loaded.
if (!process.env.JWT_SECRET) {
  process.env.JWT_SECRET = crypto.randomBytes(32).toString("hex");
  console.warn("JWT_SECRET is not set. Generated ephemeral dev secret.");
}

const connectDB = require("./config/db");
const authRoutes = require("./routes/authRoutes");
const seedManager = require("./seeders/seedManager");

const app = express();

// Allow the main recruiter app and the separate testing dashboard to
// call this API. CLIENT_ORIGIN may be a comma-separated list; the
// testing app on :5174 is always allowed.
// For development, also allow localhost and 127.0.0.1 with any port.
const envOrigins = (process.env.CLIENT_ORIGIN || "")
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);
const allowedOrigins = Array.from(
  new Set([...envOrigins, "http://localhost:5174"])
);

// Development-friendly CORS: allow localhost and 127.0.0.1 with any port
function isAllowedOrigin(origin) {
  if (!origin) return true; // Allow requests with no origin (e.g., server-to-server)
  
  // Check explicitly configured origins
  if (allowedOrigins.includes(origin)) return true;
  
  // Allow localhost with any port
  if (origin.match(/^http:\/\/localhost:\d+$/)) return true;
  
  // Allow 127.0.0.1 with any port (for browser previews)
  if (origin.match(/^http:\/\/127\.0\.0\.1:\d+$/)) return true;
  
  return false;
}

app.use(
  cors({
    origin: (origin, callback) => {
      if (isAllowedOrigin(origin)) {
        return callback(null, true);
      }
      return callback(new Error(`CORS blocked for origin: ${origin}`));
    },
    credentials: true,
  })
);
app.use(express.json());

app.get("/api/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.use("/api/auth", authRoutes);

app.use((req, res) => {
  res.status(404).json({ message: `Not found: ${req.method} ${req.originalUrl}` });
});

app.use((err, _req, res, _next) => {
  console.error("Unhandled error:", err);
  res.status(500).json({ message: "Internal server error" });
});

const PORT = process.env.PORT || 4000;

connectDB()
  .then(seedManager)
  .then(() => {
    app.listen(PORT, () => {
      console.log(`Auth API listening on http://localhost:${PORT}`);
    });
  })
  .catch((error) => {
    console.error("Failed to start server:", error.message);
    process.exit(1);
  });

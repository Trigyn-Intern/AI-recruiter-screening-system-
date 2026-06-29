const jwt = require("jsonwebtoken");
const User = require("../models/User");

async function requireAuth(req, res, next) {
  try {
    const header = req.headers.authorization || "";
    const [scheme, token] = header.split(" ");

    if (scheme !== "Bearer" || !token) {
      return res.status(401).json({ message: "Missing or invalid Authorization header." });
    }

    let payload;
    try {
      payload = jwt.verify(token, process.env.JWT_SECRET);
    } catch {
      return res.status(401).json({ message: "Session expired. Please sign in again." });
    }

    const user = await User.findById(payload.sub);
    if (!user) {
      return res.status(401).json({ message: "Account not found. Please sign in again." });
    }

    req.user = user;
    return next();
  } catch (error) {
    console.error("auth middleware error:", error);
    return res.status(500).json({ message: "Authentication failed." });
  }
}

module.exports = requireAuth;

// In-process Mongo replacement: nothing to connect to, no Docker, no
// external process. The auth backend reads its user collection from
// `backend/data/users.json`, writes are serialised through a queue so
// concurrent signups can't corrupt the file.

const path = require("path");
const fs = require("fs");
const User = require("../src/store/userStore");

const DATA_DIR = path.resolve(__dirname, "..", "data");
const USERS_FILE = path.join(DATA_DIR, "users.json");

async function connectDB() {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  if (!fs.existsSync(USERS_FILE)) {
    fs.writeFileSync(USERS_FILE, "[]", "utf-8");
  }
  await User._init();
  console.log(`In-process auth store ready at ${USERS_FILE}`);
  return { engine: "json", host: USERS_FILE, name: "auth" };
}

module.exports = connectDB;

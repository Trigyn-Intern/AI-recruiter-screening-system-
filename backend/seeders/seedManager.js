// Idempotent seeder for the manager account that gates the separate
// testing dashboard. Runs on server start.
//
// Behavior:
//   * If a user with SEED_MANAGER_EMAIL does not exist, create one using
//     the current SEED_MANAGER_PASSWORD (default: "Manager@123") and the
//     "manager" role.
//   * If a user with that email exists, refresh the stored password and
//     role from the env so operators can rotate the manager password
//     simply by editing .env and restarting the auth API. The user is
//     matched by the seeded email; existing managers are not removed.
const bcrypt = require("bcryptjs");
const path = require("path");
const User = require("../src/store/userStore");
const { JsonCollection } = require("../src/store/jsonStore");

const SEED_EMAIL = (process.env.SEED_MANAGER_EMAIL || "manager@local")
  .trim()
  .toLowerCase();
const SEED_PASSWORD = process.env.SEED_MANAGER_PASSWORD || "Manager@123";
const SEED_NAME = process.env.SEED_MANAGER_NAME || "Test Manager";

async function seedManager() {
  await User._readyNow();

  const existing = await User.findOne({ email: SEED_EMAIL });
  const hashed = await bcrypt.hash(SEED_PASSWORD, 10);

  if (existing && existing.id) {
    const doc = existing.raw || existing;
    const previousWasHashed =
      typeof doc.password === "string" && doc.password.startsWith("$2");
    const passwordMatches =
      previousWasHashed &&
      (await bcrypt.compare(SEED_PASSWORD, doc.password).catch(() => false));
    const roleMatches = doc.role === "manager";

    if (passwordMatches && roleMatches) {
      console.log(`[seed] manager up to date (${SEED_EMAIL}).`);
      return { created: false, updated: false, email: SEED_EMAIL };
    }

    // Force-refresh the stored record so the seeded credentials are
    // always honored. The User facade does not expose an update helper,
    // so we drop down to the JsonCollection directly.
    const usersFile = path.resolve(
      __dirname,
      "..",
      "data",
      "users.json"
    );
    const collection = new JsonCollection(usersFile);
    await collection._ensureLoaded();
    const cached = await collection.findOne({ email: SEED_EMAIL });
    if (cached) {
      cached.password = hashed;
      cached.role = "manager";
      if (!cached.name) cached.name = SEED_NAME;
      await collection._flush();
    }
    console.log(
      "[seed] manager credentials refreshed for " + SEED_EMAIL +
        " (password rotated from SEED_MANAGER_PASSWORD)."
    );
    return { created: false, updated: true, email: SEED_EMAIL };
  }

  const created = await User.create({
    name: SEED_NAME,
    email: SEED_EMAIL,
    password: hashed,
    role: "manager",
  });

  console.log(
    "[seed] manager account created: " + created.email +
      " (set SEED_MANAGER_PASSWORD to change the default)."
  );
  return { created: true, email: created.email };
}

module.exports = seedManager;

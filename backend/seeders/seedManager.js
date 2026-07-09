// Idempotent seeder for the manager account that gates the separate
// testing dashboard. Runs once at server start. If a user with the
// seeded email already exists, it is left alone (no password/role
// overwrite).
const bcrypt = require("bcryptjs");
const User = require("../src/store/userStore");

const SEED_EMAIL = (process.env.SEED_MANAGER_EMAIL || "manager@local")
  .trim()
  .toLowerCase();
const SEED_PASSWORD = process.env.SEED_MANAGER_PASSWORD || "Manager@123";
const SEED_NAME = process.env.SEED_MANAGER_NAME || "Test Manager";

async function seedManager() {
  await User._readyNow();

  const existing = await User.findOne({ email: SEED_EMAIL });
  if (existing && existing.id) {
    console.log(`[seed] manager already present (${SEED_EMAIL}); skipping.`);
    return { created: false, email: SEED_EMAIL };
  }

  const hashed = await bcrypt.hash(SEED_PASSWORD, 10);
  const created = await User.create({
    name: SEED_NAME,
    email: SEED_EMAIL,
    password: hashed,
    role: "manager",
  });

  console.log(
    `[seed] manager account created: ${created.email} ` +
      `(set SEED_MANAGER_PASSWORD to change the default).`,
  );
  return { created: true, email: created.email };
}

module.exports = seedManager;

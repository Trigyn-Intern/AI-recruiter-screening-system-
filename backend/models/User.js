// Backwards-compatible shim. Older code paths imported `User` from this
// directory; point them at the in-process store so we can drop mongoose
// entirely.

module.exports = require("../src/store/userStore");

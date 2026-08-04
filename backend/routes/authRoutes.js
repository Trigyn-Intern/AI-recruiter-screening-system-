const express = require("express");
const { login, me, signup } = require("../controllers/authController");
const requireAuth = require("../middleware/requireAuth");
const { validateLogin, validateSignup } = require("../middleware/validate");

const router = express.Router();

router.post("/signup", validateSignup, signup);
router.post("/login", validateLogin, login);
router.get("/me", requireAuth, me);

module.exports = router;
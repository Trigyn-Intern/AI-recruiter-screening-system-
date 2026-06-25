const EMAIL_REGEX = /^\S+@\S+\.\S+$/;

function validateSignup(req, res, next) {
  const { name, email, password, confirmPassword } = req.body || {};

  if (!name || !email || !password || !confirmPassword) {
    return res.status(400).json({ message: "Name, email, password, and confirmation are required." });
  }

  if (String(password).length < 6) {
    return res.status(400).json({ message: "Password must be at least 6 characters." });
  }

  if (password !== confirmPassword) {
    return res.status(400).json({ message: "Passwords do not match." });
  }

  if (!EMAIL_REGEX.test(String(email).trim().toLowerCase())) {
    return res.status(400).json({ message: "Please provide a valid email." });
  }

  return next();
}

function validateLogin(req, res, next) {
  const { email, password } = req.body || {};

  if (!email || !password) {
    return res.status(400).json({ message: "Email and password are required." });
  }

  if (!EMAIL_REGEX.test(String(email).trim().toLowerCase())) {
    return res.status(400).json({ message: "Please provide a valid email." });
  }

  return next();
}

module.exports = { validateSignup, validateLogin };
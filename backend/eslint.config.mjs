// ESLint v9+ flat config. Replaces the old .eslintrc.* files.
import js from "@eslint/js";

export default [
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: {
        process: "readonly", console: "readonly", Buffer: "readonly",
        __dirname: "readonly", __filename: "readonly", module: "readonly",
        require: "readonly", exports: "readonly", global: "readonly",
        URL: "readonly", URLSearchParams: "readonly",
        setTimeout: "readonly", clearTimeout: "readonly",
        setInterval: "readonly", clearInterval: "readonly", setImmediate: "readonly",
        describe: "readonly", it: "readonly", test: "readonly", expect: "readonly",
        beforeAll: "readonly", afterAll: "readonly", beforeEach: "readonly",
        afterEach: "readonly", jest: "readonly",
      },
    },
    rules: {
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      "no-console": "off",
    },
  },
  { ignores: ["node_modules/**", "coverage/**", "dist/**"] },
];

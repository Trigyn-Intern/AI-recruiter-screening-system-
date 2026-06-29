// Tiny file-backed JSON collection. Drop-in for very small datasets
// (signup, login, profile lookups). Writes are serialised through a
// single queue so concurrent `create` calls cannot lose data.

const fs = require("fs");
const path = require("path");

class JsonCollection {
  constructor(filePath, defaultDoc = () => ({})) {
    this.filePath = filePath;
    this.defaultDoc = defaultDoc;
    this._cache = [];
    this._writeQueue = Promise.resolve();
    this._loaded = false;
    this._idCounter = 0;
  }

  async _ensureLoaded() {
    if (this._loaded) return;
    try {
      const raw = await fs.promises.readFile(this.filePath, "utf-8");
      const parsed = JSON.parse(raw || "[]");
      this._cache = Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      if (err.code !== "ENOENT") throw err;
      this._cache = [];
      fs.mkdirSync(path.dirname(this.filePath), { recursive: true });
      await fs.promises.writeFile(this.filePath, "[]", "utf-8");
    }
    this._idCounter = this._cache.reduce((m, doc) => {
      const n = Number(String(doc._id).replace(/[^0-9]/g, ""));
      return Number.isFinite(n) && n > m ? n : m;
    }, 0);
    this._loaded = true;
  }

  _nextId() {
    this._idCounter += 1;
    return `u${this._idCounter.toString(36)}${Date.now().toString(36).slice(-4)}`;
  }

  async _flush() {
    const tmp = `${this.filePath}.tmp`;
    await fs.promises.writeFile(tmp, JSON.stringify(this._cache, null, 2), "utf-8");
    await fs.promises.rename(tmp, this.filePath);
  }

  _enqueue(work) {
    const next = this._writeQueue.then(work, work);
    this._writeQueue = next.catch(() => undefined);
    return next;
  }

  async insert(doc) {
    await this._ensureLoaded();
    return this._enqueue(async () => {
      const id = doc._id || this._nextId();
      const stored = { ...doc, _id: id };
      this._cache.push(stored);
      await this._flush();
      return stored;
    });
  }

  async findOne(predicate) {
    await this._ensureLoaded();
    return this._cache.find((doc) => matchDoc(doc, predicate)) || null;
  }

  async findById(id) {
    await this._ensureLoaded();
    return this._cache.find((doc) => doc._id === id) || null;
  }

  async count() {
    await this._ensureLoaded();
    return this._cache.length;
  }

  async clear() {
    this._cache = [];
    await this._enqueue(async () => {
      await fs.promises.writeFile(this.filePath, "[]", "utf-8");
    });
  }
}

function matchDoc(doc, predicate) {
  if (!predicate) return true;
  if (typeof predicate === "function") return !!predicate(doc);
  for (const key of Object.keys(predicate)) {
    if (doc[key] !== predicate[key]) return false;
  }
  return true;
}

module.exports = { JsonCollection };

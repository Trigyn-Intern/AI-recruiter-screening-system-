// Mongoose-shaped facade over the JSON collection so the controllers,
// middleware, and routes can keep using `User.findOne()`, `.select()`,
// `.create()`, `.toJSON()` etc. without changing.

const path = require("path");
const { JsonCollection } = require("./jsonStore");

const DATA_DIR = path.resolve(__dirname, "..", "..", "data");
const USERS_FILE = path.join(DATA_DIR, "users.json");

let collection = null;
let _ready = null;

function toJsonTransform(doc) {
  if (!doc) return doc;
  const { _id, password, ...rest } = doc;
  const out = { ...rest };
  if (_id !== undefined) out.id = _id;
  if (out.id === undefined && doc.id !== undefined) out.id = doc.id;
  return out;
}

function applySelect(doc, fields) {
  if (!doc) return doc;
  const id = doc._id || doc.id;
  return {
    raw: doc,
    id,
    name: doc.name,
    email: doc.email,
    role: doc.role,
    createdAt: doc.createdAt,
    get password() {
      if (!fields || fields.length === 0) return undefined;
      if (fields.includes("+password")) return doc.password;
      return undefined;
    },
    toJSON: () => toJsonTransform(doc),
  };
}

async function _init() {
  if (!collection) {
    collection = new JsonCollection(USERS_FILE);
    await collection._ensureLoaded();
  }
  return collection;
}

async function _readyNow() {
  if (_ready) return _ready;
  _ready = _init();
  return _ready;
}

// Build a chainable query that resolves to a Document-like object once
// awaited.  Supports `.select("+password")` like Mongoose.
function buildChain(executor, fields) {
  const promise = (async () => {
    await _readyNow();
    return executor();
  })();
  const thenable = promise.then((doc) => applySelect(doc, fields));
  thenable.select = function select(...names) {
    fields.push(...names);
    return thenable;
  };
  return thenable;
}

const User = {
  _init,
  _readyNow,

  findOne(query) {
    const fields = [];
    return buildChain(
      () => collection.findOne(query),
      fields
    );
  },

  async findById(id) {
    await _readyNow();
    const lookupId = String(id);
    const doc =
      await collection.findById(lookupId)
      || await collection.findOne({ id: lookupId });
    return doc ? applySelect(doc, []) : null;
  },

  async create(payload) {
    await _readyNow();
    const now = new Date().toISOString();
    const stored = await collection.insert({ ...payload, createdAt: now });
    return applySelect(stored, []);
  },

  async updateOne(query, updates) {
    await _readyNow();
    const stored = await collection.updateOne(query, updates);
    return stored ? applySelect(stored, []) : null;
  },

  async _clear() {
    await _readyNow();
    return collection.clear();
  },
};

module.exports = User;


const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

class Element {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.value = "";
    this.classList = { add() {}, remove() {} };
  }

  set innerHTML(value) {
    this.html = value;
    this.children = [];
  }

  set length(value) {
    this.children.length = value;
  }

  appendChild(child) {
    this.children.push(child);
  }

  setAttribute() {}

  addEventListener(event, handler) {
    this[event] = handler;
  }

  reset() {
    this.didReset = true;
  }
}

test("signup refreshes the roster and availability without using a cached response", async () => {
  const elements = Object.fromEntries(
    ["activities-list", "activity", "signup-form", "message", "email"].map(
      (id) => [id, new Element()]
    )
  );
  elements.activity.appendChild(new Element("option"));

  const email = "student+chess@mergington.edu";
  const activities = {
    "Chess Club": {
      description: "Play chess",
      schedule: "Friday",
      max_participants: 12,
      participants: [],
    },
  };
  const cachedActivities = JSON.stringify(activities);
  const requests = [];
  let initialize;

  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, "../src/static/app.js"), "utf8"),
    {
      document: {
        getElementById: (id) => elements[id],
        createElement: (tag) => new Element(tag),
        addEventListener: (event, handler) => { initialize = handler; },
      },
      window: {},
      console,
      setTimeout() {},
      fetch: async (url, options = {}) => {
        requests.push({ url, options });
        if (options.method === "POST") {
          activities["Chess Club"].participants.push(email);
          return { ok: true, json: async () => ({ message: "Signed up" }) };
        }
        const body = options.cache === "no-store"
          ? JSON.stringify(activities)
          : cachedActivities;
        return { ok: true, json: async () => JSON.parse(body) };
      },
    }
  );

  initialize();
  await new Promise((resolve) => setImmediate(resolve));
  elements.email.value = email;
  elements.activity.value = "Chess Club";

  let preventedDefault = false;
  await elements["signup-form"].submit({
    preventDefault() { preventedDefault = true; },
  });

  assert.equal(preventedDefault, true);
  assert.equal(requests.filter(({ url }) => url === "/activities").length, 2);
  const card = elements["activities-list"].children[0];
  const participants = card.children[0];
  assert.equal(participants.children[0].textContent, "Participants (1)");
  assert.equal(participants.children[1].children[0].children[0].textContent, email);
  assert.match(card.html, /11 spots left/);
  assert.equal(elements.activity.children.length, 2);
  assert.equal(elements["signup-form"].didReset, true);
  assert.equal(elements.message.className, "success");
});

test("only the latest activity refresh updates the roster", async () => {
  const elements = Object.fromEntries(
    ["activities-list", "activity", "signup-form", "message", "email"].map(
      (id) => [id, new Element()]
    )
  );
  elements.activity.appendChild(new Element("option"));

  const pendingRequests = [];
  let initialize;
  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, "../src/static/app.js"), "utf8"),
    {
      document: {
        getElementById: (id) => elements[id],
        createElement: (tag) => new Element(tag),
        addEventListener: (event, handler) => { initialize = handler; },
      },
      window: {},
      console,
      setTimeout() {},
      fetch: (url, options = {}) => {
        if (options.method === "POST") {
          return Promise.resolve({
            ok: true,
            json: async () => ({ message: "Signed up" }),
          });
        }
        return new Promise((resolve, reject) => {
          pendingRequests.push({ resolve, reject });
        });
      },
    }
  );

  const activities = (name) => ({
    [name]: {
      description: "Activity",
      schedule: "Friday",
      max_participants: 12,
      participants: [],
    },
  });
  const response = (name) => ({
    ok: true,
    json: async () => activities(name),
  });
  const submitSignup = () => elements["signup-form"].submit({
    preventDefault() {},
  });

  initialize();
  const olderRefresh = submitSignup();
  await new Promise((resolve) => setImmediate(resolve));
  pendingRequests[1].resolve(response("Newest Activity"));
  await olderRefresh;
  pendingRequests[0].resolve(response("Older Activity"));
  await new Promise((resolve) => setImmediate(resolve));
  assert.match(elements["activities-list"].children[0].html, /Newest Activity/);

  const staleFailedRefresh = submitSignup();
  await new Promise((resolve) => setImmediate(resolve));
  const latestRefresh = submitSignup();
  await new Promise((resolve) => setImmediate(resolve));
  pendingRequests[3].resolve(response("Latest Activity"));
  await latestRefresh;
  pendingRequests[2].reject(new Error("Stale request failed"));
  await staleFailedRefresh;
  assert.match(elements["activities-list"].children[0].html, /Latest Activity/);
});
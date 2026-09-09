const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

const source = fs.readFileSync(
  path.join(__dirname, "../../web/js/screens.js"),
  "utf8",
);
const context = {
  window: {},
  App: { state: { view: "home", char: { job_id: "novice" } } },
  API: {},
  document: { querySelector: () => null, querySelectorAll: () => [] },
  localStorage: { getItem: () => null, setItem: () => {} },
};
vm.runInNewContext(source, context);

test("accepts a new event cursor even when the batch id is unchanged", () => {
  const home = context.window.Screens.home;
  home._queue = [];
  home._shown = [];
  home._lastBatch = null;
  home._lastEventCursor = null;
  home._combatState = "idle";

  const event = { kind: "attack", actor: "勇者", target: "波利", damage: 1 };
  home._ingest({
    hunt_state: "active", combat_state: "combat", batch_id: "b1",
    event_cursor: "c1", events: [event], retreated: false,
  });
  home._ingest({
    hunt_state: "active", combat_state: "combat", batch_id: "b1",
    event_cursor: "c2", events: [{ ...event, damage: 2 }], retreated: false,
  });

  assert.equal(home._queue.length, 2);
  assert.equal(home._lastEventCursor, "c2");
});

test("does not mark an eventless active hunt as combat", () => {
  const home = context.window.Screens.home;
  home._queue = [];
  home._shown = [];
  home._lastBatch = null;
  home._lastEventCursor = null;
  home._combatState = "idle";

  home._ingest({
    hunt_state: "active", combat_state: "hunting", batch_id: null,
    event_cursor: null, events: [], retreated: false,
  });

  assert.equal(home._combatState, "hunting");
});

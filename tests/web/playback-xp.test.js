const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

function load(file, extra = {}) {
  const context = {
    window: {},
    Screens: {},
    App: { state: { view: "home", char: { job_id: "novice" } } },
    API: {},
    document: { querySelector: () => null, querySelectorAll: () => [] },
    localStorage: { getItem: () => null, setItem: () => {} },
    ...extra,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, file), "utf8"), context);
  return context.window;
}

test("30-round manual MVP playback has a real-time floor", () => {
  const view = load("../../web/js/screen-more.js").ROFightView;
  assert.equal(typeof view.playbackDelayMs, "function");
  const delay = view.playbackDelayMs(30, 60);
  assert.ok(delay >= 300);
  assert.ok(delay * 60 >= 20000);
});

test("XP percentage clamps zero, normal, and max-level boundaries", () => {
  const view = load("../../web/js/screens.js").XP;
  const plain = (value) => JSON.parse(JSON.stringify(value));
  assert.deepEqual(plain(view.progress(0, 0)), { current: 0, next: 0, percent: 0 });
  assert.deepEqual(plain(view.progress(25, 100)), { current: 25, next: 100, percent: 25 });
  assert.deepEqual(plain(view.progress(150, 100)), { current: 150, next: 100, percent: 100 });
  assert.deepEqual(plain(view.progress(0, 0, true)), { current: 0, next: 0, percent: 100 });
});

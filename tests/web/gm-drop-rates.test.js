const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

function loadApi(fetchImpl) {
  const source = fs.readFileSync(path.join(__dirname, "../../web/js/api.js"), "utf8");
  const storage = new Map();
  const context = {
    fetch: fetchImpl,
    localStorage: {
      getItem: (key) => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, String(value)),
      removeItem: (key) => storage.delete(key),
    },
  };
  vm.runInNewContext(`${source}\nthis.__API = API;`, context);
  return context.__API;
}

test("drop-rate API wrappers preserve optional scope and exact request payload", async () => {
  const calls = [];
  const api = loadApi(async (url, options) => {
    calls.push({ url, options });
    return {
      status: 200,
      ok: true,
      json: async () => ({ effective_rate: 0.25 }),
    };
  });

  await api.adminDropRates("angel_poring_card", "angel_poring");
  await api.adminDropRates();
  await api.adminSetDropRate("angel_poring_card", 0.25, "angel_poring");
  await api.adminDeleteDropRate("angel_poring_card", "angel_poring");

  assert.equal(calls[0].url, "/api/admin/drop-rates?item_id=angel_poring_card&source_id=angel_poring");
  assert.equal(calls[1].url, "/api/admin/drop-rates");
  assert.equal(calls[2].url, "/api/admin/drop-rates");
  assert.deepEqual(JSON.parse(calls[2].options.body), {
    item_id: "angel_poring_card",
    source_id: "angel_poring",
    rate: 0.25,
  });
  assert.equal(calls[3].url, "/api/admin/drop-rates?item_id=angel_poring_card&source_id=angel_poring");
});

test("drop-rate helpers search names and ids and enforce the API rate range", () => {
  const source = fs.readFileSync(path.join(__dirname, "../../web/js/screen-more.js"), "utf8");
  const context = { window: {}, Screens: {} };
  vm.runInNewContext(source, context);

  const catalog = {
    monsters: { poring: { id: "poring", name: "波利" } },
    mvps: { angel_poring: { id: "angel_poring", name: "天使波利" } },
    equipment: { angel_wing: { id: "angel_wing", name: "天使之翼" } },
    cards: { angel_poring_card: { id: "angel_poring_card", name: "天使波利卡片" } },
  };

  assert.deepEqual(
    JSON.parse(JSON.stringify(context.window.RODropRateView.searchCatalog(catalog, "天使"))),
    {
      sources: [{ id: "angel_poring", name: "天使波利", kind: "mvp" }],
      items: [
        { id: "angel_poring_card", name: "天使波利卡片", kind: "card" },
        { id: "angel_wing", name: "天使之翼", kind: "equipment" },
      ],
    },
  );
  assert.equal(context.window.RODropRateView.isValidRate(0), true);
  assert.equal(context.window.RODropRateView.isValidRate(1), true);
  assert.equal(context.window.RODropRateView.isValidRate(-0.01), false);
  assert.equal(context.window.RODropRateView.isValidRate(1.01), false);
  assert.equal(context.window.RODropRateView.isValidRate(Number.NaN), false);
  assert.equal(context.window.RODropRateView.isValidRate(""), false);
});

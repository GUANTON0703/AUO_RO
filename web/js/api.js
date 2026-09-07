// ROtxt web API client. Same-origin fetch wrapper + all endpoints.
const API = (() => {
  const TOKEN_KEY = "rotxt_token";
  let token = localStorage.getItem(TOKEN_KEY) || null;

  function setToken(t) {
    token = t || null;
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  }

  async function req(method, path, body) {
    const headers = {};
    if (token) headers["Authorization"] = "Bearer " + token;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const resp = await fetch("/api" + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (resp.status === 204) return null;
    let data = null;
    try { data = await resp.json(); } catch (_) {}
    if (!resp.ok) {
      const detail = (data && (data.detail || data.message)) || resp.statusText;
      const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      err.status = resp.status;
      err.detail = detail;
      throw err;
    }
    return data;
  }
  const get = (p) => req("GET", p);
  const post = (p, b) => req("POST", p, b === undefined ? {} : b);
  const put = (p, b) => req("PUT", p, b);
  const del = (p) => req("DELETE", p);

  return {
    get token() { return token; },
    setToken,
    hasToken: () => !!token,

    // auth
    register: (invite_code, username, password) =>
      post("/accounts", { invite_code, username, password }),
    login: async (username, password) => {
      const b = await post("/sessions", { username, password });
      setToken(b.token);
      return b;
    },
    logout: async () => { try { await del("/sessions"); } finally { setToken(null); } },
    me: () => get("/me"),

    // characters / progression
    listCharacters: () => get("/characters"),
    createCharacter: (name) => post("/characters", { name }),
    deleteCharacter: (cid) => del("/characters/" + cid),
    sheet: (cid) => get(`/characters/${cid}/sheet`),
    inventory: (cid) => get(`/characters/${cid}/inventory`),
    allocateStats: (cid, deltas) => post(`/characters/${cid}/stats`, deltas),
    learnSkill: (cid, skill_id, level) => post(`/characters/${cid}/skills`, { skill_id, level }),
    resetStats: (cid) => post(`/characters/${cid}/resetstats`),
    resetSkills: (cid) => post(`/characters/${cid}/resetskills`),
    jobchange: (cid, target_job_id) => post(`/characters/${cid}/jobchange`, { target_job_id }),

    // hunt
    huntStart: (map_id, monster_ids) => post("/hunt/start", { map_id, monster_ids: monster_ids || [] }),
    huntStatus: () => get("/hunt/status"),
    huntStop: () => post("/hunt/stop"),
    huntStrategy: (cid) => get("/hunt/strategy/" + cid),
    setHuntStrategy: (cid, strat) => put("/hunt/strategy/" + cid, strat),

    // inventory ops
    equip: (cid, eqInstanceId) =>
      post(`/characters/${cid}/inventory/equip`, { equipment_instance_id: eqInstanceId }),
    unequip: (cid, slot) => post(`/characters/${cid}/inventory/unequip`, { slot }),
    refine: (cid, eqInstanceId) =>
      post(`/characters/${cid}/inventory/refine`, { equipment_instance_id: eqInstanceId }),
    socket: (cid, eqInstanceId, cardItemId) =>
      post(`/characters/${cid}/inventory/socket`,
           { equipment_instance_id: eqInstanceId, card_item_id: cardItemId }),

    // shop / storage
    shop: () => get("/shop"),
    buy: (item_id, qty) => post("/shop/buy", { item_id, qty: qty || 1 }),
    sell: (payload) => post("/shop/sell", payload),
    storage: () => get("/storage"),
    deposit: (payload) => post("/storage/deposit", payload),
    withdraw: (payload) => post("/storage/withdraw", payload),

    // social
    leaderboard: (by) => get("/leaderboard?by=" + encodeURIComponent(by || "base_level")),
    chatSince: (channel, after) =>
      get(`/chat?channel=${encodeURIComponent(channel)}&after=${after || 0}`),
    chatPost: (channel, text) => post("/chat", { channel, text }),
    guildMine: () => get("/guild/mine"),
    guildList: () => get("/guild"),
    guildCreate: (name) => post("/guild", { name }),
    guildJoin: (gid) => post(`/guild/${gid}/join`),
    guildLeave: () => post("/guild/leave"),

    // mvp
    listMvp: () => get("/mvp"),
    challengeMvp: (mvp_id, flee_hp_frac) =>
      post("/mvp/challenge", flee_hp_frac == null ? { mvp_id } : { mvp_id, flee_hp_frac }),

    // trade
    tradePending: () => get("/trade/pending"),
    tradeOffer: (to_username) => post("/trade/offer", { to_username }),
    tradeGet: (tid) => get("/trade/" + tid),
    tradePut: (tid, payload) => post(`/trade/${tid}/put`, payload),
    tradeConfirm: (tid) => post(`/trade/${tid}/confirm`),
    tradeCancel: (tid) => post(`/trade/${tid}/cancel`),

    // content / admin
    catalog: () => get("/content/catalog"),
    adminSettings: () => get("/admin/settings"),
    adminSetMultipliers: (experience, drop, zeny) =>
      put("/admin/settings/multipliers", { experience, drop, zeny }),
    adminSetHunt: (settle_floor_seconds, huntable_win_rate) =>
      put("/admin/settings/hunt", { settle_floor_seconds, huntable_win_rate }),
    adminMoney: (cid, amount) => post(`/admin/characters/${cid}/money`, { amount }),
    adminExperience: (cid, base_exp, job_exp) =>
      post(`/admin/characters/${cid}/experience`, { base_exp, job_exp }),
    adminOnlinePlayers: () => get("/admin/online-players"),
  };
})();

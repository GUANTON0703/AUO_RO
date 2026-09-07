// ROtxt web — boot, auth, navigation shell, hunt polling.
const App = (() => {
  const state = {
    char: null,        // CharacterPublic of the active character
    catalog: null,     // static content pack (loaded once)
    me: null,          // { is_gm, ... }
    view: "home",
    poll: null,        // setInterval id for hunt polling
    huntSecs: 0, huntSecsAt: 0,   // client-side interpolation of 掛機時間
    chatLast: 0,
  };

  const $ = (s) => document.querySelector(s);

  function toast(msg, bad) {
    const el = $("#toast");
    el.textContent = msg;
    el.className = "toast" + (bad ? " bad" : "");
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => (el.hidden = true), 2600);
  }

  function showScreen(id) {
    document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
    $("#app").hidden = true;
    if (id === "app") { $("#app").hidden = false; return; }
    $("#" + id).classList.add("active");
  }

  async function boot() {
    wireAuth();
    if (API.hasToken()) {
      try {
        await loadGame();
        return;
      } catch (e) {
        API.setToken(null);
      }
    }
    showScreen("screen-auth");
  }

  function wireAuth() {
    document.querySelectorAll("[data-authtab]").forEach((b) => {
      b.onclick = () => {
        document.querySelectorAll("[data-authtab]").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        const t = b.dataset.authtab;
        $("#form-login").hidden = t !== "login";
        $("#form-register").hidden = t !== "register";
      };
    });
    $("#form-login").onsubmit = async (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      try {
        await API.login(f.get("username"), f.get("password"));
        await loadGame();
      } catch (err) { toast(err.detail || "登入失敗", true); }
    };
    $("#form-register").onsubmit = async (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      try {
        await API.register(f.get("invite_code"), f.get("username"), f.get("password"));
        await API.login(f.get("username"), f.get("password"));
        await loadGame();
      } catch (err) { toast(err.detail || "註冊失敗", true); }
    };
    $("#form-newchar").onsubmit = async (e) => {
      e.preventDefault();
      const name = new FormData(e.target).get("name");
      try {
        state.char = await API.createCharacter(name);
        await loadGame();
      } catch (err) { toast(err.detail || "建立失敗", true); }
    };
  }

  async function loadGame() {
    const chars = await API.listCharacters();
    if (!chars.length) { showScreen("screen-newchar"); return; }
    state.char = chars[0];
    state.catalog = state.catalog || (await API.catalog());
    try { state.me = await API.me(); } catch (_) { state.me = { is_gm: false }; }

    showScreen("app");
    wireNav();
    navigate("home");
  }

  function wireNav() {
    document.querySelectorAll("#nav [data-nav]").forEach((b) => {
      b.onclick = () => navigate(b.dataset.nav);
    });
  }

  async function refreshChar() {
    try {
      const chars = await API.listCharacters();
      const fresh = chars.find((c) => c.id === state.char.id);
      if (fresh) state.char = fresh;
    } catch (_) {}
  }

  function startHuntPoll() {
    stopHuntPoll();
    state.poll = setInterval(tickHunt, 2500);
    tickHunt();
  }
  function stopHuntPoll() {
    if (state.poll) clearInterval(state.poll);
    state.poll = null;
  }

  async function tickHunt() {
    let status = null;
    try { status = await API.huntStatus(); }
    catch (e) {
      // 沒在掛機 → 停止輪詢（避免每 2.5 秒打一次 409）
      if (e.status === 409) { stopHuntPoll(); status = null; }
      else return;
    }
    if (status) {
      const s = Number(status.effective_seconds || 0);
      if (s !== state.huntSecs) { state.huntSecs = s; state.huntSecsAt = Date.now(); }
      if (status.retreated) { stopHuntPoll(); }
    }
    await refreshChar();
    if (state.view === "home") Screens.home.render(status);
  }

  function huntSecsShown() {
    if (!state.huntSecsAt) return state.huntSecs;
    return state.huntSecs + (Date.now() - state.huntSecsAt) / 1000;
  }

  async function navigate(view) {
    state.view = view;
    document.querySelectorAll("#nav [data-nav]").forEach((b) =>
      b.classList.toggle("active", b.dataset.nav === view));
    const scr = Screens[view];
    $("#view").innerHTML = `<div class="spinner">載入中…</div>`;
    if (view !== "home") {
      stopHuntPoll();                       // home.mount 自己決定要不要輪詢
      if (Screens.home && Screens.home._stopDrip) Screens.home._stopDrip();
      if (Screens.home && Screens.home._stopChat) Screens.home._stopChat();
    }
    if (view !== "more" && Screens.more && Screens.more._stopFightDrip) Screens.more._stopFightDrip();
    if (!scr || !scr.mount) {
      $("#view").innerHTML = `<div class="card"><p class="muted">這個畫面還沒做。</p></div>`;
      return;
    }
    try {
      await scr.mount();
    } catch (e) {
      $("#view").innerHTML = `<div class="card">出錯了：${e.detail || e.message}</div>`;
    }
  }

  return { state, toast, navigate, boot, refreshChar,
           huntSecsShown, startHuntPoll, stopHuntPoll };
})();

document.addEventListener("DOMContentLoaded", App.boot);

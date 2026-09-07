// screen-social — 排行榜 / 世界聊天 / 公會
(() => {
  const LB_OPTS = [
    ["base_level", "Base 等級"],
    ["job_level", "Job 等級"],
    ["zeny", "Zeny"],
    ["cards", "卡片收藏"],
    ["refine", "最高精煉"],
  ];

  function msgHtml(m) {
    return `<div><span class="dim">${esc(m.character_name)}：</span>${esc(m.text)}</div>`;
  }

  // 增量拉：只抓 seen 之後的，append 進去、上限 200 行。reset=true 重頭來一次。
  async function pollChannel(channel, box, seenKey, holder, reset) {
    if (!box || S.view !== "social") return;
    if (reset) { holder[seenKey] = 0; box.innerHTML = ""; delete box.dataset.empty; }
    let msgs;
    try { msgs = await API.chatSince(channel, holder[seenKey] || 0); }
    catch (_) { return; }
    for (const m of msgs) holder[seenKey] = Math.max(holder[seenKey] || 0, m.id);
    if (msgs.length) {
      if (box.dataset.empty) { box.innerHTML = ""; delete box.dataset.empty; }
      box.insertAdjacentHTML("beforeend", msgs.map(msgHtml).join(""));
      while (box.children.length > 200) box.removeChild(box.firstChild);
      box.scrollTop = box.scrollHeight;
    } else if (!box.children.length && !box.dataset.empty) {
      box.innerHTML = "<span class='dim'>還沒有訊息</span>";
      box.dataset.empty = "1";
    }
  }

  Screens.social = {
    _stale() { return S.view !== "social"; },
    async mount() {
      clearInterval(this._timer);
      this._timer = null;
      this._lbBy = this._lbBy || "base_level";
      this._worldSeen = 0;
      this._guildSeen = 0;

      view().innerHTML = `
        <div class="card">
          <div class="section-title"><h3>排行榜</h3>
            <select id="lb-by">${LB_OPTS.map(([v, t]) =>
              `<option value="${v}"${v === this._lbBy ? " selected" : ""}>${t}</option>`).join("")}</select>
          </div>
          <div class="list" id="lb-list"><div class="spinner">載入中…</div></div>
        </div>

        <div class="card">
          <h3>世界頻道</h3>
          <div class="log" id="world-log"><span class="dim">載入中…</span></div>
          <div class="row" style="margin-top:8px">
            <input id="world-input" placeholder="說點什麼…" maxlength="200" style="flex:1">
            <button class="btn primary" id="world-send">送出</button>
          </div>
        </div>

        <div class="card" id="guild-card">
          <h3>公會</h3>
          <div id="guild-body"><div class="spinner">載入中…</div></div>
        </div>`;

      const sel = document.querySelector("#lb-by");
      sel.onchange = () => { this._lbBy = sel.value; this._loadBoard(); };
      this._loadBoard();

      const wIn = document.querySelector("#world-input");
      const wSend = document.querySelector("#world-send");
      const send = async () => {
        const t = wIn.value.trim();
        if (!t) return;
        wSend.disabled = true;
        try {
          await API.chatPost("world", t);
          wIn.value = "";
          await this._pollWorld(true);
        } catch (e) { App.toast(e.detail || "送出失敗", true); }
        wSend.disabled = false;
      };
      wSend.onclick = send;
      wIn.onkeydown = (e) => { if (e.key === "Enter") send(); };

      await this._pollWorld(true);
      await this._loadGuild();

      this._timer = setInterval(() => {
        if (S.view !== "social") { clearInterval(this._timer); this._timer = null; return; }
        this._pollWorld(false);
        if (this._guildId) this._pollGuild(false);
      }, 5000);
    },

    async _loadBoard() {
      const box = document.querySelector("#lb-list");
      try {
        const rows = await API.leaderboard(this._lbBy);
        if (this._stale()) return;
        box.innerHTML = rows.length
          ? rows.map((r, i) =>
              `<div class="item"><div>${i + 1}. ${esc(r.character_name)}
                <div class="sub">${esc(r.account)}</div></div>
                <strong>${esc(r.value ?? 0)}</strong></div>`).join("")
          : "<p class='muted'>沒有資料</p>";
      } catch (e) { box.innerHTML = `<p class="muted">${esc(e.detail || "載入失敗")}</p>`; }
    },

    async _pollWorld(reset) {
      await pollChannel("world", document.querySelector("#world-log"),
                        "_worldSeen", this, reset);
    },

    async _loadGuild() {
      const body = document.querySelector("#guild-body");
      let mine = null;
      try { mine = await API.guildMine(); } catch (_) {}
      if (this._stale()) return;
      if (mine) {
        this._guildId = mine.id;
        body.innerHTML = `
          <div class="section-title"><strong>${esc(mine.name)}</strong>
            <button class="btn small" id="guild-leave">離開</button></div>
          <p class="muted">成員 ${mine.members ? mine.members.length : 1} 人</p>
          <div class="log" id="guild-log"><span class="dim">載入中…</span></div>
          <div class="row" style="margin-top:8px">
            <input id="guild-input" placeholder="公會頻道…" maxlength="200" style="flex:1">
            <button class="btn primary" id="guild-send">送出</button>
          </div>`;
        document.querySelector("#guild-leave").onclick = async () => {
          if (!confirm("確定離開公會？")) return;
          try { await API.guildLeave(); App.toast("已離開公會"); this._guildId = null; await this._loadGuild(); }
          catch (e) { App.toast(e.detail || "失敗", true); }
        };
        const gIn = document.querySelector("#guild-input");
        const gSend = document.querySelector("#guild-send");
        const ch = "guild:" + mine.id;
        const send = async () => {
          const t = gIn.value.trim();
          if (!t) return;
          gSend.disabled = true;
          try { await API.chatPost(ch, t); gIn.value = ""; await this._pollGuild(true); }
          catch (e) { App.toast(e.detail || "送出失敗", true); }
          gSend.disabled = false;
        };
        gSend.onclick = send;
        gIn.onkeydown = (e) => { if (e.key === "Enter") send(); };
        await this._pollGuild(true);
      } else {
        this._guildId = null;
        let list = [];
        try { list = await API.guildList(); } catch (_) {}
        if (this._stale()) return;
        body.innerHTML = `
          <div class="row" style="margin-bottom:10px">
            <input id="guild-name" placeholder="公會名稱" maxlength="32" style="flex:1">
            <button class="btn primary" id="guild-create">建立</button>
          </div>
          <div class="list" id="guild-list">${
            list.length
              ? list.map((g) => `<div class="item"><div>${esc(g.name)}
                  <div class="sub">${g.member_count ?? 0} 人</div></div>
                  <button class="btn small" data-join="${g.id}">加入</button></div>`).join("")
              : "<p class='muted'>還沒有公會</p>"}</div>`;
        document.querySelector("#guild-create").onclick = async () => {
          const name = document.querySelector("#guild-name").value.trim();
          if (!name) return;
          try { await API.guildCreate(name); App.toast("公會已建立"); await this._loadGuild(); }
          catch (e) { App.toast(e.detail || "建立失敗", true); }
        };
        body.querySelectorAll("[data-join]").forEach((b) => {
          b.onclick = async () => {
            try { await API.guildJoin(Number(b.dataset.join)); App.toast("已加入"); await this._loadGuild(); }
            catch (e) { App.toast(e.detail || "加入失敗", true); }
          };
        });
      }
    },

    async _pollGuild(reset) {
      if (!this._guildId) return;
      await pollChannel("guild:" + this._guildId, document.querySelector("#guild-log"),
                        "_guildSeen", this, reset);
    },
  };
})();

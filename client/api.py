class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f"[{status}] {detail}")
        self.status = status
        self.detail = detail


class ApiClient:
    def __init__(self, http, token: str | None = None):
        self._http = http
        self.token = token

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _req(self, method: str, path: str, **kw):
        resp = self._http.request(method, path, headers=self._headers(), **kw)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise ApiError(resp.status_code, str(detail))
        return resp.json() if resp.content else None

    # --- auth ---
    def register(self, invite_code, username, password):
        return self._req(
            "POST",
            "/api/accounts",
            json={"invite_code": invite_code, "username": username, "password": password},
        )

    def login(self, username, password):
        body = self._req("POST", "/api/sessions", json={"username": username, "password": password})
        self.token = body["token"]
        return body

    def logout(self):
        self._req("DELETE", "/api/sessions")
        self.token = None

    # --- characters ---
    def list_characters(self):
        return self._req("GET", "/api/characters")

    def create_character(self, name):
        return self._req("POST", "/api/characters", json={"name": name})

    def sheet(self, cid):
        return self._req("GET", f"/api/characters/{cid}/sheet")

    def delete_character(self, cid):
        return self._req("DELETE", f"/api/characters/{cid}")

    def allocate_stats(self, cid, deltas):
        return self._req("POST", f"/api/characters/{cid}/stats", json=deltas)

    def learn_skill(self, cid, skill_id, level):
        return self._req(
            "POST", f"/api/characters/{cid}/skills", json={"skill_id": skill_id, "level": level}
        )

    def jobchange(self, cid, target):
        return self._req(
            "POST", f"/api/characters/{cid}/jobchange", json={"target_job_id": target}
        )

    def reset_stats(self, cid):
        return self._req("POST", f"/api/characters/{cid}/resetstats")

    def reset_skills(self, cid):
        return self._req("POST", f"/api/characters/{cid}/resetskills")

    # --- hunt ---
    def hunt_start(self, map_id, monster_ids=None):
        b = {"map_id": map_id}
        if monster_ids is not None:   # 空 list 也要送：代表「明確自動」，清掉舊指定
            b["monster_ids"] = monster_ids
        return self._req("POST", "/api/hunt/start", json=b)

    def hunt_status(self):
        return self._req("GET", "/api/hunt/status")

    def hunt_stop(self):
        return self._req("POST", "/api/hunt/stop")

    def hunt_strategy(self, cid):
        return self._req("GET", f"/api/hunt/strategy/{cid}")

    def set_hunt_strategy(self, cid, strategy):
        return self._req("PUT", f"/api/hunt/strategy/{cid}", json=strategy)

    # --- mvp ---
    def list_mvp(self):
        return self._req("GET", "/api/mvp")

    def challenge_mvp(self, mvp_id, flee_hp_frac=None):
        b = {"mvp_id": mvp_id}
        if flee_hp_frac is not None:
            b["flee_hp_frac"] = flee_hp_frac
        return self._req("POST", "/api/mvp/challenge", json=b)

    # --- inventory ---
    def inventory(self, cid):
        return self._req("GET", f"/api/characters/{cid}/inventory")

    def equip(self, cid, inst_id):
        return self._req(
            "POST",
            f"/api/characters/{cid}/inventory/equip",
            json={"equipment_instance_id": inst_id},
        )

    def unequip(self, cid, slot):
        return self._req(
            "POST", f"/api/characters/{cid}/inventory/unequip", json={"slot": slot}
        )

    def socket(self, cid, inst_id, card_id):
        return self._req(
            "POST",
            f"/api/characters/{cid}/inventory/socket",
            json={"equipment_instance_id": inst_id, "card_item_id": card_id},
        )

    def refine(self, cid, inst_id):
        return self._req(
            "POST",
            f"/api/characters/{cid}/inventory/refine",
            json={"equipment_instance_id": inst_id},
        )

    # --- shop / storage ---
    def shop(self):
        return self._req("GET", "/api/shop")

    # --- player content query ---
    def content_monster(self, monster_id):
        return self._req("GET", f"/api/content/monsters/{monster_id}")

    def content_item(self, item_id):
        return self._req("GET", f"/api/content/items/{item_id}")

    def content_card(self, card_id):
        return self._req("GET", f"/api/content/cards/{card_id}")

    def content_equipment(self, equipment_id):
        return self._req("GET", f"/api/content/equipment/{equipment_id}")

    def buy(self, item_id, qty=1):
        return self._req("POST", "/api/shop/buy", json={"item_id": item_id, "qty": qty})

    def sell(self, item_id=None, qty=1, equipment_instance_id=None):
        b = {"qty": qty}
        if item_id:
            b["item_id"] = item_id
        if equipment_instance_id:
            b["equipment_instance_id"] = equipment_instance_id
        return self._req("POST", "/api/shop/sell", json=b)

    def storage(self):
        return self._req("GET", "/api/storage")

    def deposit(self, **b):
        return self._req("POST", "/api/storage/deposit", json=b)

    def withdraw(self, **b):
        return self._req("POST", "/api/storage/withdraw", json=b)

    # --- social: leaderboard ---
    def leaderboard(self, by="base_level"):
        return self._req("GET", "/api/leaderboard", params={"by": by})

    # --- social: chat ---
    def chat_post(self, channel, text):
        return self._req("POST", "/api/chat", json={"channel": channel, "text": text})

    def chat_since(self, channel, after=0):
        return self._req("GET", "/api/chat", params={"channel": channel, "after": after})

    # --- social: trade ---
    def trade_offer(self, to_username):
        return self._req("POST", "/api/trade/offer", json={"to_username": to_username})

    def trade_put(self, tid, **kw):
        return self._req("POST", f"/api/trade/{tid}/put", json=kw)

    def trade_confirm(self, tid):
        return self._req("POST", f"/api/trade/{tid}/confirm")

    def trade_cancel(self, tid):
        return self._req("POST", f"/api/trade/{tid}/cancel")

    def trade_pending(self):
        return self._req("GET", "/api/trade/pending")

    def trade_get(self, tid):
        return self._req("GET", f"/api/trade/{tid}")

    # --- social: guild ---
    def guild_create(self, name):
        return self._req("POST", "/api/guild", json={"name": name})

    def guild_join(self, gid):
        return self._req("POST", f"/api/guild/{gid}/join")

    def guild_leave(self):
        return self._req("POST", "/api/guild/leave")

    def guild_mine(self):
        return self._req("GET", "/api/guild/mine")

    def guild_list(self):
        return self._req("GET", "/api/guild")

# 二轉 B 分支 + 60–99 內容 + 轉生二轉 計畫

## 目標

1. 補完 v1 職業樹 —— 每個一轉的第二個二轉分支（設計文件 6.2 本來就規劃了，只做了一半）。
2. 填 60–99 的怪物 / 地圖 / 裝備 / 卡片 / MVP（等級上限剛開到 99，這段是空的）。
3. 補上轉生二轉（Transcendent）—— 資料先爬文備好，機制與實作獨立一期。

## 現況

- 職業：新手 + 一轉 ×6 + 二轉 ×6（只有 A 分支：騎士 / 巫師 / 獵人 / 牧師 / 鐵匠 / 刺客）。
- 缺的二轉 B 分支：十字軍、賢者、吟遊詩人（詩人 / 舞孃合併，ROtxt 無性別）、武僧、鍊金術師、流氓。
- 地圖：5 城（普隆德拉 / 夢羅克 / 拜昂 / 吉芬 / 阿爾迪巴朗），約 40 張圖，最高段約 lv 55–60。
- 技能 effect 詞彙固定：physical_hit / magic_hit / aoe / heal_hp / heal_sp / buff / debuff / passive_stat / proc。trigger：passive / every_turn / cooldown_ready / sp_available / hp_below_50 / hp_below_30。
- 每職 4–6 個代表技能，不搬整棵 RO 技能樹。

## 分工

- **Codex（爬文 + 出規格文件，純新增 `docs/`，不碰程式，避免 worktree 撞車）**：
  - 從 Pre-Renewal RO 資料庫爬 6 個 B 分支職業 + 12 個轉生二轉的：代表技能、技能效果數值、屬性成長、轉職門檻。
  - 產出 `docs/job-data/<job>.md`，每個職業一頁，格式對齊現有 skills.src.json 的欄位。
- **Claude + sonnet 子代理（在 main 實作）**：從 Codex 的規格文件把資料寫進 `data/`，接框架、平衡、驗收。

## Phase 1 — 二轉 B 分支（6 職業）

不需動戰鬥引擎，全是資料 + 驗證。

- **Batch 1**：`data/jobs.json` 加 6 個 job 條目（parent、tier=second、change_job_level、hp/sp_per_level 對齊 A 分支同儕）。
- **Batch 2**：`data/skills.src.json` 加 6 × 4–6 技能 → `build_skills.py` → `check_skills.py` 過。RO 招式映射到現有 effect 詞彙（例：阿斯普迪歐→buff aspd；魔法震撼→magic_hit；狂暴獻祭→proc）。
- **Batch 3**：每職一場 combat smoke（`_graduated_*` 等級的角色能正常打、技能有發動），調 change_job_level 與成長係數。
- 前端 `screen-build.js` 轉職分頁已經吃 `jobs` 的 parent_id，B 分支會自動出現在「轉職」選項，不用改。

## Phase 2 — 60–99 內容

- **Batch 4**：`data/monsters.src.json` 加 lv 55–99 段怪物（經典 RO 高等區：格拉斯神殿深層、龜島、尼夫赫姆、니플헤임、Rachel / 冰洞、深淵湖、Thanatos 塔、Bio Labs、Juperos）。用 `build_monsters.py` 生成。
- **Batch 5**：`data/maps.json` 加對應地圖 + region（可能要加新 town，例如 rachel / lighthalzen / hugel）。
- **Batch 6**：`data/equipment.json` + `data/cards.json` 加該段裝備與卡片 + 掉落表。`check_content.py` 過（每張卡都要有怪能掉）。
- **Batch 7**：`data/mvps.json` 加該段 MVP。

## Phase 3 — 轉生二轉（獨立一期，1+2 做完再開）

需要先設計「重生」機制，不只是資料：

- 重生流程：角色滿 99 → 變 High 新手 → 重練到 99 → 轉生二轉。
- 要決定：重生後等級歸 1 還是保留？額外屬性點 / HP-SP 加成？屬性上限拉高（99 → ?）。
- job 系統加 tier=transcendent，12 個新 job + ~60 技能。
- Codex 的爬文資料這期直接用。

## 已知技術債

- **高等 MVP 防禦被測試樣本壓低**：`test_mvp_beatable_by_geared_same_level_player` 用通用劍士 + 對應等級 tier 裝，但 `physical_damage` 在高防禦區間掉得很陡，lv85+ 的 MVP（turtle_general/yao_jun 填 88、maero/apocalypse/valkyrie 填 85）defense 都遠低於 `baseline(lv,"boss")`（~100–120）。真正的修法：樣本帶 MVP 對應的屬性/種族卡，或檢視傷害公式在高防禦的曲線，或這些 MVP 本來就不該是純肉牆。之後專門一批處理。

## 開放問題

1. 重生機制走經典硬重置（1 級 / 微量加成）還是寬鬆版（保留等級 / 大加成）？
2. Phase 3 排在 1+2 之後，還是要平行推？
3. 60–99 新增 town 的命名 / 視覺識別（沿用官方地名還是自訂）。

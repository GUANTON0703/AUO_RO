# 神行太保 stalker

## 職業數值
- parent: rogue
- change_job_level: 50
- hp_per_level / sp_per_level: 8.0 / 2.5
- 定位: 強化版流氓，以隱匿、偷取裝備與技能模仿干擾敵人。

## 代表技能（挑 5 個）
- `preserve` / 技能保留 / active；max_level: 1；效果: buff, stat=max_sp, 幅度=[10]%, duration_s=600；sp_cost=[30]；原版對應招式名: Preserve（以防止模仿技能被覆寫近似）
- `full_strip` / 全身剝奪 / active；max_level: 5；效果: debuff, stat=def, 幅度=[-10,-20,-30,-40,-50]%, duration_s=30；sp_cost=[15,18,21,24,27]；原版對應招式名: Full Strip（以降低 DEF 近似）
- `intimidate` / 威脅 / active；max_level: 5；效果: physical_hit, power_pct=[130,160,190,220,250]；sp_cost=[10,12,14,16,18]；原版對應招式名: Intimidate
- `reject_sword` / 拒絕劍術 / active；max_level: 5；效果: buff, stat=def, 幅度=[10,20,30,40,50]%, duration_s=60；sp_cost=[10,10,10,10,10]；原版對應招式名: Reject Sword
- `plagiarism` / 技能模仿 / passive；max_level: 10；效果: proc, effect=copy_last_enemy_skill, chance_pct=[100,100,100,100,100,100,100,100,100,100]；sp_cost=[0,0,0,0,0,0,0,0,0,0]；原版對應招式名: Plagiarism（轉生後仍是核心特色）

資料來源：<https://irowiki.org/classic/Stalker>、<https://irowiki.org/wiki/Stalker>

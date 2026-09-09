# 流氓 rogue

## 職業數值
- parent: thief
- change_job_level: 40
- hp_per_level / sp_per_level: 7.5 / 2.0
- 定位: 以短劍、弓、偷竊與模仿技能靈活作戰的干擾型近戰職。

## 代表技能（挑 5 個）
- `sword_mastery` / 劍術修練 / passive；max_level: 10；效果: passive_stat, stat=atk, amount=[4,8,12,16,20,24,28,32,36,40]；sp_cost=[0,0,0,0,0,0,0,0,0,0]；原版對應招式名: Sword Mastery
- `raid` / 背刺 / active；max_level: 5；效果: physical_hit, power_pct=[200,250,300,350,400]；sp_cost=[10,12,14,16,18]；原版對應招式名: Raid／Back Stab（以單體背刺近似）
- `snatch` / 自動偷竊 / passive；max_level: 10；效果: proc, effect=steal_loot, chance_pct=[5,7,9,11,13,15,17,19,21,23]；sp_cost=[0,0,0,0,0,0,0,0,0,0]；原版對應招式名: Gank／Snatcher
- `plagiarism` / 技能模仿 / passive；max_level: 10；效果: proc, effect=copy_last_enemy_skill, chance_pct=[100,100,100,100,100,100,100,100,100,100]；sp_cost=[0,0,0,0,0,0,0,0,0,0]；原版對應招式名: Plagiarism（以觸發複製近似）
- `sightless_mind` / 無影之牙 / active；max_level: 5；效果: physical_hit, power_pct=[140,180,220,260,300]；sp_cost=[20,22,24,26,28]；原版對應招式名: Sightless Mind

資料來源：<https://irowiki.org/classic/Rogue>、<https://irowiki.org/wiki/Rogue>

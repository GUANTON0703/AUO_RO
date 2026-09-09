# 領主騎士 lord_knight

## 職業數值
- parent: knight
- change_job_level: 50
- hp_per_level / sp_per_level: 12.0 / 1.5
- 定位: 強化版騎士，兼具高耐久、騎乘長矛與狂暴近戰輸出。

## 代表技能（挑 5 個）
- `parry` / 劍術格擋 / active；max_level: 10；效果: buff, stat=def, 幅度=[5,10,15,20,25,30,35,40,45,50]%, duration_s=60；sp_cost=[50,50,50,50,50,50,50,50,50,50]；原版對應招式名: Parrying
- `spiral_pierce` / 螺旋擊刺 / active；max_level: 5；效果: physical_hit, power_pct=[200,250,300,350,400]；sp_cost=[18,21,24,27,30]；原版對應招式名: Spiral Pierce
- `clashing_spiral` / 螺旋刺擊 / active；max_level: 5；效果: physical_hit, power_pct=[180,220,260,300,340]；sp_cost=[15,18,21,24,27]；原版對應招式名: Clashing Spiral
- `berserk` / 狂暴狀態 / active；max_level: 1；效果: buff, stat=atk, 幅度=[100]%, duration_s=60；sp_cost=[200]；原版對應招式名: Berserk
- `aura_blade` / 靈氣劍 / passive；max_level: 5；效果: passive_stat, stat=atk, amount=[5,10,15,20,25]；sp_cost=[0,0,0,0,0]；原版對應招式名: Aura Blade

資料來源：<https://irowiki.org/classic/Lord_Knight>、<https://ragnaplace.com/en/wiki/irowiki-classic/Transcendent>

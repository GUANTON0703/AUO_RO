# 高階牧師 high_priest

## 職業數值
- parent: priest
- change_job_level: 50
- hp_per_level / sp_per_level: 8.0 / 4.5
- 定位: 強化版牧師，負責治療、復活、聖屬性驅魔與全隊增益。

## 代表技能（挑 5 個）
- `meditatio` / 冥想 / passive；max_level: 10；效果: passive_stat, stat=max_sp, amount=[20,40,60,80,100,120,140,160,180,200]；sp_cost=[0,0,0,0,0,0,0,0,0,0]；原版對應招式名: Meditatio
- `assumptio` / 聖母之頌歌 / active；max_level: 5；效果: buff, stat=def, 幅度=[10,20,30,40,50]%, duration_s=60；sp_cost=[20,25,30,35,40]；原版對應招式名: Assumptio
- `coluceo_heal` / 群體治癒 / active；max_level: 5；效果: heal_hp, flat=[180,260,340,420,500]；sp_cost=[40,45,50,55,60]；原版對應招式名: Highness Heal（以固定 HP 治療近似）
- `medial_vulgata` / 聖母之頌歌 / active；max_level: 5；效果: heal_hp, flat=[120,180,240,300,360]；sp_cost=[25,30,35,40,45]；原版對應招式名: Medial Vulgata（以範圍治療近似）
- `basilica` / 聖域 / active；max_level: 5；效果: buff, stat=def, 幅度=[15,20,25,30,35]%, duration_s=30；sp_cost=[80,90,100,110,120]；原版對應招式名: Basilica

資料來源：<https://irowiki.org/classic/High_Priest>、<https://irowiki.org/wiki/High_Priest>

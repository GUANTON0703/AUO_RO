# 吟遊詩人 bard

## 職業數值
- parent: archer
- change_job_level: 40
- hp_per_level / sp_per_level: 7.0 / 2.5
- 定位: 遠程攻擊與團隊歌曲支援；ROtxt 無性別，合併詩人與舞孃的代表技能。

## 代表技能（挑 5 個）
- `musical_strike` / 樂器攻擊 / active；max_level: 5；效果: physical_hit, power_pct=[120,140,160,180,200]；sp_cost=[3,4,5,6,7]；原版對應招式名: Musical Strike
- `arrow_vulcan` / 箭矢風暴 / active；max_level: 10；效果: physical_hit, power_pct=[200,240,280,320,360,400,440,480,520,560]；sp_cost=[12,14,16,18,20,22,24,26,28,30]；原版對應招式名: Arrow Vulcan
- `poem_of_bragi` / 布萊奇之詩 / active；max_level: 10；效果: buff, stat=aspd, 幅度=[5,10,15,20,25,30,35,40,45,50]%, duration_s=60；sp_cost=[20,22,24,26,28,30,32,34,36,38]；原版對應招式名: Poem of Bragi（以 ASPD 支援近似）
- `service_for_you` / 為你服務 / active；max_level: 10；效果: buff, stat=max_sp, 幅度=[5,10,15,20,25,30,35,40,45,50]%, duration_s=60；sp_cost=[20,22,24,26,28,30,32,34,36,38]；原版對應招式名: Service for You
- `scream` / 驚聲尖叫 / active；max_level: 5；效果: debuff, stat=flee, 幅度=[-5,-10,-15,-20,-25]%, duration_s=10；sp_cost=[12,14,16,18,20]；原版對應招式名: Dazzler／Scream（以降低 FLEE 近似暈眩）

資料來源：<https://irowiki.org/classic/Bard>、<https://irowiki.org/classic/Dancer>

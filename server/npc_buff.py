"""NPC 代喝套裝 buff：牧師/高階牧師/吟遊詩人整套技能效果打包成一次性服務，
不是真實道具，跟掛機頁「租一次」「持續租用」共用這組常數。"""

ITEM_ID = "npc_buff_rental"
NAME = "NPC 代喝套裝 buff"
STATS = {"atk": 20, "matk": 15, "hit": 10, "flee": 10, "aspd": 10, "regen_bonus_pct": 20}
ONE_TIME_COST = 5000
ONE_TIME_DURATION_S = 300
HOURLY_COST = 8000
HOURLY_INTERVAL_S = 3600

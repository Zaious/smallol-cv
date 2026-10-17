# 隊伍資料檔的原始資料（Leaguepedia）：選手個人資料，以及每人參加過的一級賽事與名次（本地算冠軍、世界賽次數、出道年份）。
# 可續傳：已存在的檔案不重抓。Leaguepedia 限流嚴重時以環境變數 LP_GAP 加大請求間隔。
# 前置：data/lp/w26_players.json（Worlds 2026 TournamentPlayers）
# 用法：LP_GAP=30 python tools/teamsheet_fetch.py
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__)); from lp_fetch import cargo, OUT
sys.stdout.reconfigure(encoding="utf-8")
tp = json.load(open(os.path.join(OUT, "w26_players.json"), encoding="utf-8"))
links = sorted({r["Link"] for r in tp if r["Link"]})
q = lambda xs: ",".join("'" + x.replace("'", "''") + "'" for x in xs)
print("人數", len(links), flush=True)
for i in range(0, len(links), 60):                         # 分批，避免網址過長
    part = links[i:i + 60]; tag = f"_{i // 60}"
    if not os.path.exists(os.path.join(OUT, f"ts_players{tag}.json")):
        cargo(f"ts_players{tag}", tables="Players", fields="OverviewPage,ID,Player,Name,NativeName,Nationality,Country,Birthdate,Residency,Role,IsSubstitute",
              where=f"OverviewPage IN ({q(part)})")
    if not os.path.exists(os.path.join(OUT, f"ts_career{tag}.json")):
        # 每人參加過的一級賽事（含世界賽），附該隊在該賽事的名次（沒有名次資料時為空）
        cargo(f"ts_career{tag}", tables="TournamentPlayers=TP,Tournaments=T,TournamentResults=TR",
              join_on="TP.OverviewPage=T.OverviewPage,TP.OverviewPage=TR.OverviewPage",
              fields="TP.Link=Link,TP.Team=Team,TR.Team=ResTeam,TR.Place=Place,T.Name=Name,T.League=League,T.Year=Year,T.DateStart=DateStart",
              where=f"TP.Link IN ({q(part)}) AND T.TournamentLevel='Primary' AND (TR.Team IS NULL OR TR.Team=TP.Team)")
    print("批次", i // 60, "完成", flush=True)
print("全部完成", flush=True)

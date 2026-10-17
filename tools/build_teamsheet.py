# 隊伍資料檔：Worlds 2026 各隊的種子、晉級途徑、先發／替補／教練，以及選手簡介（只用有出處的事實組句，不寫自由描述）。
# 輸入（Leaguepedia，tools/lp_fetch.py、teamsheet_fetch.py 抓）：data/lp/w26_seeds.json、w26_players.json、ts_players_*.json、ts_career_*.json
#       本服務的歷史資料：data/archive/players.json（本屆實際上場局數）
# 輸出：data/archive/teamsheet.json（服務以 /teams.json 提供）。資料不齊時照樣產出，缺的欄位為 null。
# 用法：python tools/build_teamsheet.py
import json, os, glob, datetime as dt
from collections import Counter, defaultdict
ROOT = os.path.join(os.path.dirname(__file__), ".."); LP = os.path.join(ROOT, "data", "lp"); A = os.path.join(ROOT, "data", "archive")
TODAY = dt.date(2026, 10, 17)
# Leaguepedia 晉級表的隊伍代號 → (報名名單隊名, 官方代碼)
TEAMS = {"GEN": ("Gen.G", "GEN"), "HLE": ("Hanwha Life Esports", "HLE"), "T1": ("T1", "T1"), "Dplus": ("Dplus Kia", "DK"),
         "AL CN": ("Anyone's Legend", "AL"), "BLG": ("Bilibili Gaming", "BLG"), "TES": ("Top Esports", "TES"), "IG": ("Invictus Gaming", "IG"),
         "TL": ("Team Liquid", "TL"), "LYON24": ("LYON (2024 American Team)", "LYON"), "G2": ("G2 Esports", "G2"), "MKOI": ("Movistar KOI", "MKOI"),
         "TSTW": ("Team Secret Whales", "TSW"), "CFO": ("CTBC Flying Oyster", "CFO"), "LOS": ("LØS", "LOS"),
         "C9": ("Cloud9", "C9"), "KCORP": ("Karmine Corp", "KC"), "MVK": ("MVK Esports", "MVK"), "FURIA": ("FURIA", "FUR")}
LEAGUE = {"Korea": "LCK", "China": "LPL", "North America": "LCS", "EMEA": "LEC", "Asia-Pacific": "LCP", "Brazil": "CBLOL"}
ROLE = {"Top": "top", "Jungle": "jungle", "Mid": "mid", "Bot": "bottom", "Support": "support"}
NAT = {"South Korea": "韓國", "China": "中國", "Taiwan": "台灣", "Vietnam": "越南", "Brazil": "巴西", "United States": "美國", "Canada": "加拿大",
       "Denmark": "丹麥", "France": "法國", "Germany": "德國", "Spain": "西班牙", "Poland": "波蘭", "Sweden": "瑞典", "Belgium": "比利時",
       "Japan": "日本", "Hong Kong": "香港", "Australia": "澳洲", "Philippines": "菲律賓", "Thailand": "泰國", "Malaysia": "馬來西亞",
       "United Kingdom": "英國", "Netherlands": "荷蘭", "Turkey": "土耳其", "Russia": "俄羅斯", "Czech Republic": "捷克", "Slovenia": "斯洛維尼亞",
       "Lithuania": "立陶宛", "Greece": "希臘", "Italy": "義大利", "Portugal": "葡萄牙", "Argentina": "阿根廷", "Chile": "智利", "Mexico": "墨西哥",
       "Peru": "秘魯", "Croatia": "克羅埃西亞", "Bulgaria": "保加利亞", "Romania": "羅馬尼亞", "Hungary": "匈牙利", "Austria": "奧地利",
       "Switzerland": "瑞士", "Norway": "挪威", "Finland": "芬蘭", "Israel": "以色列", "Macau": "澳門", "Singapore": "新加坡", "Indonesia": "印尼",
       "Uruguay": "烏拉圭", "Colombia": "哥倫比亞", "Ukraine": "烏克蘭", "Serbia": "塞爾維亞", "Slovakia": "斯洛伐克", "Ireland": "愛爾蘭"}
TITLE_LEAGUES = {"World Championship": "世界賽", "Mid-Season Invitational": "MSI", "LoL Champions Korea": "LCK", "Tencent LoL Pro League": "LPL",
                 "LoL EMEA Championship": "LEC", "LoL European Championship": "LEC", "LoL Championship Series": "LCS", "League Championship Series": "LCS",
                 "LoL Championship Pacific": "LCP", "Pacific Championship Series": "PCS", "Vietnam Championship Series": "VCS",
                 "Campeonato Brasileiro de League of Legends": "CBLOL", "League of Legends Japan League": "LJL", "LTA North": "LTA North", "LTA South": "LTA South"}

def load_all(prefix):
    rows = []
    for p in sorted(glob.glob(os.path.join(LP, f"{prefix}_*.json"))): rows += json.load(open(p, encoding="utf-8"))
    return rows

def age(bd):
    try: b = dt.date.fromisoformat(bd[:10]); return TODAY.year - b.year - ((TODAY.month, TODAY.day) < (b.month, b.day))
    except Exception: return None

def main():
    seeds = json.load(open(os.path.join(LP, "w26_seeds.json"), encoding="utf-8"))
    tp = json.load(open(os.path.join(LP, "w26_players.json"), encoding="utf-8"))
    bios = {r["OverviewPage"]: r for r in load_all("ts_players")}
    career = defaultdict(list)
    for r in load_all("ts_career"): career[r["Link"]].append(r)
    played = {}
    try:
        for name, e in json.load(open(os.path.join(A, "players.json"), encoding="utf-8"))["players"].items():
            played[(e["team"], name.split(" ", 1)[-1].lower())] = len(e["games"])
    except Exception: pass
    out = []
    for s in seeds:
        if s["lpTeam"] not in TEAMS: continue
        tname, code = TEAMS[s["lpTeam"]]; lg = LEAGUE.get(s["region"])
        # Leaguepedia 回傳時欄位名的底線會變空格
        roster = sorted([r for r in tp if r["Team"] == tname], key=lambda r: int(r.get("N PlayerInTeam") or r.get("N_PlayerInTeam") or 99))
        players, coaches, seen_role = [], [], Counter()
        for r in roster:
            link = r["Link"]; b = bios.get(link, {}); pid = r["Player"]
            if r["Role"] not in ROLE:
                coaches.append({"id": pid, "role": r["Role"], "nationality": NAT.get(r["Flag"], r["Flag"])}); continue
            role = ROLE[r["Role"]]; seen_role[role] += 1
            c = career.get(link, [])
            years = sorted({int(x["Year"]) for x in c if (x.get("Year") or "").isdigit()})
            worlds = sorted({int(x["Year"]) for x in c if x.get("League") == "World Championship" and (x.get("Year") or "").isdigit()})
            titles = Counter(TITLE_LEAGUES[x["League"]] for x in c if x.get("Place") == "1" and x.get("League") in TITLE_LEAGUES)
            a = age(b.get("Birthdate") or ""); nat = NAT.get(r["Flag"], r["Flag"]) or None
            debut = years[0] if years else None
            n_worlds = len(set(worlds) | {2026}) if c else None      # 含本屆
            parts = [x for x in (nat, f"{a} 歲" if a else None, f"{debut} 年出道" if debut else None,
                                 f"第 {n_worlds} 次打世界賽" if n_worlds else None) if x]
            if titles: parts.append("、".join(f"{k}冠軍 ×{v}" for k, v in sorted(titles.items(), key=lambda kv: (kv[0] != "世界賽", kv[0] != "MSI", -kv[1]))))
            players.append({"id": pid.split(" (")[0], "link": link, "role": role, "starter": seen_role[role] == 1,
                            "name": b.get("Name") or None, "nativeName": b.get("NativeName") or None, "nationality": nat, "age": a,
                            "debutYear": debut, "worldsAppearances": n_worlds, "worldsYears": worlds or None, "titles": dict(titles) or None,
                            "gamesThisWorlds": played.get((code, pid.split(" (")[0].lower())),
                            "bio": "，".join(parts) if parts else None})
        out.append({"code": code, "name": tname.replace(" (2024 American Team)", ""), "region": s["region"], "league": lg,
                    "seed": s["seed"], "seedLabel": f"{lg} #{s['seed']}" if lg and s["seed"].isdigit() else None,
                    "startStage": s["stage"], "qualificationPath": s["path"], "players": players, "coaches": coaches})
    have_bio = sum(1 for t in out for p in t["players"] if p["age"] is not None)
    have_career = sum(1 for t in out for p in t["players"] if p["debutYear"] is not None)
    data = {"updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "tournament": "Worlds 2026", "teams": out,
            "coverage": {"teams": len(out), "players": sum(len(t["players"]) for t in out), "withBirthdate": have_bio, "withCareer": have_career},
            "sources": "Leaguepedia（晉級表、報名名單、選手資料、賽事成績）；gamesThisWorlds 為本服務記錄的本屆上場局數",
            "notes": "starter 依報名名單的順序（每個位置第一位為先發）；bio 只由 nationality、age、debutYear、worldsAppearances、titles 組成"}
    json.dump(data, open(os.path.join(A, "teamsheet.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("隊伍", len(out), "選手", data["coverage"]["players"], "有生日", have_bio, "有生涯", have_career)
    return data

if __name__ == "__main__":
    import sys; sys.stdout.reconfigure(encoding="utf-8")
    d = main()
    for t in d["teams"][:3] + [x for x in d["teams"] if x["code"] == "KC"]:
        print(t["code"], t["seedLabel"], t["startStage"], "|", t["qualificationPath"])
        for p in t["players"]: print("   ", p["role"], p["id"], "先發" if p["starter"] else "替補", "|", p["bio"], "| 本屆", p["gamesThisWorlds"])
        print("    教練", [(c["id"], c["role"]) for c in t["coaches"]])

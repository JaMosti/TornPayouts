import requests
import subprocess
from datetime import datetime, timezone
import time
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path


# --- Edit
enemy_faction = 13421               # id of enemy faction - Copy from url
war_from = "16:00:09 07/11/25"      # Chain died - Copy from faction log
war_to = "09:00:25 08/11/25"        # War start - Copy from faction log
key = "etrgwAdkvDZgHC8W"            # https://www.torn.com/preferences.php#tab=api
raid_factor_during_war = 1            # Price for raid hit
raid_factor_after_war = 1             # Price for raid hit
payout_factor = 0.7                 # How much goes to members

# --- Configuration ---
url = "https://api.torn.com/v2/faction/members"
faction_id = 9176   # The Iron Fist ID
chain_milestones = [25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]
chain_points =     [20, 40, 80, 160, 320, 640, 1280, 2560, 5120, 10240, 20480, 40960]
all_respect = 0
dt = datetime.strptime(war_from, "%H:%M:%S %d/%m/%y").replace(tzinfo=timezone.utc)
timestamp_from = dt.timestamp()
dt = datetime.strptime(war_to, "%H:%M:%S %d/%m/%y").replace(tzinfo=timezone.utc)
timestamp_to = dt.timestamp()
output_data = dict()
params = {
    "timestamp": timestamp_to,
    "key": key
}

# === Get war data
url = f"https://api.torn.com/v2/faction/rankedwars?filters=outgoing&limit=10&sort=ASC&to={timestamp_to}&from={timestamp_from}"
response = requests.get(url, params=params)
data = response.json()
wars = data["rankedwars"]
this_war = None
for war in wars:
    if war["factions"][0]["id"] in [faction_id, enemy_faction] and \
        war["factions"][1]["id"] in [faction_id, enemy_faction]:
        this_war = war
        break
else:
    print("No war found")
    os.exit(0)

enemy_name = ""
did_we_won = this_war["winner"] == faction_id
war_end = this_war["end"]
war_from = this_war["start"]
url = f"https://api.torn.com/v2/faction/{this_war["id"]}/rankedwarreport"
response = requests.get(url, params=params)
data = response.json()
report = data["rankedwarreport"]
rewards = []
for faction in report["factions"]:
    if faction["id"] == faction_id:
        # === Get rewards
        for reward in faction["rewards"]["items"]:
            rewards.append([reward["id"], reward["quantity"]])

        # === Get members
        for member in faction["members"]:
            output_data[member["id"]] = {
                "id": member["id"],
                "name": member["name"],
                "attacks_war": 0,
                "respect_war": 0,
                "attacks_raid": 0,
                "respect_raid": 0,
                "respect_raid_adj": 0,
                "adjusted_respect": 0,
                "attacks_below_2_ff": 0,
                "assists": 0,
                "overseas": 0,
                "payout": 0,
                "payout_str": "",
            }
    else:
        enemy_name = faction["name"]

# === Count total payout
total_payout = 0
for reward in rewards:
    url = f"https://api.torn.com/v2/market/{reward[0]}/itemmarket/"
    response = requests.get(url, params=params)
    data = response.json()
    item = data["itemmarket"]
    total_payout += item["item"]["average_price"] * reward[1]
    pay_str = str(item["item"]["average_price"])
    pay_new = [t if i % 3 or not i else f"{t}," for i, t in enumerate(pay_str[::-1])]
    reward.append("".join(reversed(pay_new)))

payout = total_payout * payout_factor
pay_str = str(int(payout))
pay_new = [t if i % 3 or not i else f"{t}," for i, t in enumerate(pay_str[::-1])]
payout_str = "".join(reversed(pay_new))
# === Get Hits
url = "https://api.torn.com/v2/faction/attacks"
next_link = f"{url}?filters=outgoing&limit=100&sort=ASC&to={timestamp_to}&from={timestamp_from}"
aaa = set()
while(next_link):
    try:
        response = requests.get(next_link, params=params)
        data = response.json()
        if "attacks" in data:
            attacks = data["attacks"]
            for attack in attacks:

                if attack['chain'] in chain_milestones:
                    respect_gain = 10
                else:
                    respect_gain = attack['respect_gain']

                if attack["is_ranked_war"] or attack["is_raid"]:
                    if respect_gain:
                        if attack["is_ranked_war"]:
                            output_data[attack["attacker"]["id"]]["attacks_war"] += 1
                            adj = respect_gain if int(war_end) > int(attack["started"]) else 0
                            output_data[attack["attacker"]["id"]]["respect_war"] += adj
                        elif attack["is_raid"]:
                            output_data[attack["attacker"]["id"]]["attacks_raid"] += 1
                            output_data[attack["attacker"]["id"]]["respect_raid"] += respect_gain
                            adj = respect_gain * raid_factor_during_war \
                                    if int(war_end) > int(attack["started"]) \
                                    else respect_gain * raid_factor_after_war
                            output_data[attack["attacker"]["id"]]["respect_raid_adj"] += respect_gain

                        # Other stats
                        output_data[attack["attacker"]["id"]]["overseas"] += attack["modifiers"]["overseas"] > 1
                        output_data[attack["attacker"]["id"]]["attacks_below_2_ff"] += attack["modifiers"]["fair_fight"] < 2
                    
                    output_data[attack["attacker"]["id"]]["assists"] += attack["result"] == "Assist"

        next_link = data["_metadata"]["links"]["next"]
        if len(attacks) < 100:
            next_link = None
    except Exception as e:
        print(e)
        print("Sleeping for 30 sec")
        time.sleep(30)

# === Get payout
for member in output_data:
    output_data[member]["adjusted_respect"] = output_data[member]["respect_war"] + output_data[member]["respect_raid_adj"]
    all_respect += output_data[member]["adjusted_respect"]
for member in output_data:
    output_data[member]["payout"] = int(payout/all_respect*output_data[member]["adjusted_respect"])
    pay_str = str(output_data[member]["payout"])
    pay_new = [t if i % 3 or not i else f"{t}," for i, t in enumerate(pay_str[::-1])]
    output_data[member]["payout_str"] = "".join(reversed(pay_new))
    output_data[member]["respect_war"] = int(output_data[member]["respect_war"])
    output_data[member]["respect_raid"] = int(output_data[member]["respect_raid"])
    output_data[member]["adjusted_respect"] = int(output_data[member]["adjusted_respect"])

# === Get supports
supports = [[output_data[member]["assists"], member, output_data[member]["name"]] for member in output_data if output_data[member]["assists"]]
supports.sort(key=lambda x: x[0], reverse=True)
# === Get baby bullies
bullies = [[output_data[member]["attacks_below_2_ff"], output_data[member]["attacks_war"]+output_data[member]["attacks_raid"], member, output_data[member]["name"]] for member in output_data]
bullies.sort(key=lambda x: x[0], reverse=True)
# === Get globertrotters
globertrotters = [[output_data[member]["overseas"], member, output_data[member]["name"]] for member in output_data if output_data[member]["overseas"]]
globertrotters.sort(key=lambda x: x[0], reverse=True)

# === Save to htmls
columns = list(next(iter(output_data.values())).keys())
table = sorted(list(output_data.values()), key=lambda x: x['payout'], reverse=True)
tables = [table]
if len(table) > 50:
    tables = [table[:50], table[50:]]
env = Environment(
    loader=FileSystemLoader(searchpath="."),   # looks in current directory
    autoescape=select_autoescape(["html", "xml"])
)
template = env.get_template("template.html")
html_str = template.render(
    title   = f"War agains {enemy_name} report",
    victory = did_we_won,
    rewards  = rewards,
    payout  = payout_str,
    columns = columns,
    tables  = tables,
    supports  = supports[:30],
    bullies  = bullies[:30],
    globertrotters  = globertrotters[:30],
)
 
out_path = Path("table.html").resolve()
out_path.write_text(html_str, encoding="utf-8")
enemy_name = enemy_name.replace(" ", "_")
subprocess.run(f"weasyprint.exe table.html payouts_{enemy_name}.pdf")
# os.remove("table.html")

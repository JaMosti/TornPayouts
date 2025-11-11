import requests
import subprocess
from datetime import datetime, timezone
import time
import os
import sys
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from math import ceil, floor
import tkinter as tk
from tkinter import ttk, messagebox
import traceback
import threading

application_path = ""
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
elif __file__:
    application_path = os.path.dirname(__file__)

def main():
    try:
        values = [var.get() for var in text_vars]
        enemy_faction = values[0]             # id of enemy faction - Copy from url
        war_from = values[1]      # Chain died - Copy from faction log
        war_to = values[2]        # War start - Copy from faction log
        key = values[3]            # https://www.torn.com/preferences.php#tab=api
        raid_factor_during_war = values[4] / 100            # Price for raid hit
        raid_factor_after_war = values[5] / 100             # Price for raid hit
        payout_factor = values[6] / 100                 # How much goes to members

        # --- Validate input
        try:
            datetime.strptime(war_from, "%H:%M:%S %d/%m/%y")
        except ValueError:
            messagebox.showerror("Error", "Starting time is faulty!\nMake sure it matches: %H:%M:%S %d/%m/%y\ne.g. 09:00:25 08/11/25")
            return 1
        try:
            datetime.strptime(war_to, "%H:%M:%S %d/%m/%y")
        except ValueError:
            messagebox.showerror("Error", "Ending time is faulty!\nMake sure it matches: %H:%M:%S %d/%m/%y\ne.g. 09:00:25 08/11/25")
            return 1
        if raid_factor_during_war > 1 or raid_factor_during_war < 0:
            messagebox.showerror("Error", "Raid payout factor during war is faulty!\nMake sure it's a number between 0 and 100")
            return 1
        if raid_factor_after_war > 1 or raid_factor_after_war < 0:
            messagebox.showerror("Error", "Raid payout factor after war is faulty!\nMake sure it's a number between 0 and 100")
            return 1
        if payout_factor > 1 or payout_factor < 0:
            messagebox.showerror("Error", "Members cut is faulty!\nMake sure it's a number between 0 and 100")
            return 1
        if not key:
            messagebox.showerror("Error", "Api key is empty!\n Generate \"Limited Access\" on following page:\nhttps://www.torn.com/preferences.php#tab=api")
            return 1

        # --- Configuration ---
        public_mode =  True
        url = "https://api.torn.com/v2/faction/members"
        faction_id = 9176   # The Iron Fist ID
        chain_milestones = [25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]
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
        war_lenght = int((timestamp_to - timestamp_from) / 3600)
        hits_treshold_upgrade = ceil(war_lenght/3*5)
        hits_treshold_downgrade = floor(war_lenght/4*5) * (not public_mode)

        # === Get war data
        url = f"https://api.torn.com/v2/faction/rankedwars?filters=outgoing&limit=10&sort=ASC&to={timestamp_to}&from={timestamp_from}"
        response = requests.get(url, params=params, timeout=1000)
        data = response.json()
        if data.get("error", None):
            if data["error"]["code"] == 2:
                messagebox.showerror("Error", "Api key is faulty! Generate \"Limited Access\" on following page:\nhttps://www.torn.com/preferences.php#tab=api")
            else:
                messagebox.showerror("Error", data["error"]["error"])
            return 1
        wars = data["rankedwars"]
        this_war = None
        for war in wars:
            if war["factions"][0]["id"] in [faction_id, enemy_faction] and \
                war["factions"][1]["id"] in [faction_id, enemy_faction]:
                this_war = war
                break
        else:
            messagebox.showerror("Error", "No war found! Check War ID")
            return 1

        enemy_name = ""
        did_we_won = this_war["winner"] == faction_id
        war_end = this_war["end"]
        war_from = this_war["start"]
        url = f"https://api.torn.com/v2/faction/{this_war['id']}/rankedwarreport"
        response = requests.get(url, params=params, timeout=1000)
        data = response.json()
        if data.get("error", None):
            messagebox.showerror("Error", data["error"]["error"])
            return 1
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
                        "respect_war": 0,
                        "respect_leaked": 0,
                        "respect_raid": 0,
                        "respect_raid_adj": 0,
                        "adjusted_respect": 0,
                        "attacks_below_2_ff": 0,
                        "attacks": 0,
                        "outside_attacks": 0,
                        "chain_watcher": 0,
                        "assists": 0,
                        "retaliation": 0,
                        "overseas": 0,
                        "payout": 0,
                        "payout_str": "",
                    }
            else:
                enemy_name = faction["name"]
        best_saves = []
        # === Count total payout
        total_payout = 0
        for reward in rewards:
            url = f"https://api.torn.com/v2/market/{reward[0]}/itemmarket/"
            response = requests.get(url, params=params, timeout=1000)
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
        prev_attack_timestamp = timestamp_from
        while(next_link):
            er_nr = 0
            try:
                response = requests.get(next_link, params=params, timeout=1000)
                data = response.json()
                if "attacks" in data:
                    attacks = data["attacks"]
                    for attack in attacks:
                        if attack['chain'] in chain_milestones:
                            respect_gain = 10
                        else:
                            respect_gain = attack['respect_gain']

                        if respect_gain:
                            if attack["is_ranked_war"]:
                                output_data[attack["attacker"]["id"]]["attacks"] += 1
                                adj = respect_gain if int(war_end) > int(attack["started"]) else 0
                                output_data[attack["attacker"]["id"]]["respect_war"] += adj
                            elif attack["is_raid"]:
                                output_data[attack["attacker"]["id"]]["attacks"] += 1
                                output_data[attack["attacker"]["id"]]["respect_raid"] += respect_gain
                                adj = respect_gain * raid_factor_during_war \
                                        if int(war_end) > int(attack["started"]) \
                                        else respect_gain * raid_factor_after_war
                                output_data[attack["attacker"]["id"]]["respect_raid_adj"] += adj
                            else:
                                output_data[attack["attacker"]["id"]]["outside_attacks"] += 1
                                
                            if attack["chain"] > 10:
                                chain_timer = 300 - (attack["ended"] - prev_attack_timestamp)
                                if chain_timer > 0 and chain_timer < 120: # Chain saved
                                    output_data[attack["attacker"]["id"]]["chain_watcher"] += 1
                                    best_saves.append(
                                        [
                                        f"{chain_timer//60}:{chain_timer%60:02d}",
                                        attack["attacker"]["id"],
                                        attack["attacker"]["name"],
                                        chain_timer
                                        ]
                                    )

                            if attack["is_ranked_war"] or attack["is_raid"]:
                                output_data[attack["attacker"]["id"]]["overseas"] += attack["modifiers"]["overseas"] > 1 # Overseas
                                if attack["modifiers"]["retaliation"] > 1:
                                    output_data[attack["attacker"]["id"]]["retaliation"] += 1 # retaliation
                                else:
                                    output_data[attack["attacker"]["id"]]["attacks_below_2_ff"] += attack["modifiers"]["fair_fight"] < 2 # Below 2 FF
                        if attack["is_ranked_war"] or attack["is_raid"]:
                            output_data[attack["attacker"]["id"]]["assists"] += attack["result"] == "Assist" # Assists
                        prev_attack_timestamp = attack["ended"]
                            
                next_link = data["_metadata"]["links"]["next"]
                if len(attacks) < 100:
                    next_link = None
            except Exception as e:
                er_nr += 1
                if er_nr >= 2:
                    raise e
                time.sleep(30)
                
        # === Get Leaks
        url = "https://api.torn.com/v2/faction/attacks"
        next_link = f"{url}?filters=incoming&limit=100&sort=ASC&to={timestamp_to}&from={timestamp_from}"
        while(next_link):
            try:
                response = requests.get(next_link, params=params, timeout=1000)
                data = response.json()
                if "attacks" in data:
                    attacks = data["attacks"]
                    for attack in attacks:
                        if attack["is_ranked_war"]:
                            output_data[attack["defender"]["id"]]["respect_leaked"] += attack["respect_gain"]

                next_link = data["_metadata"]["links"]["next"]
                if len(attacks) < 100:
                    next_link = None
            except Exception as e:
                er_nr += 1
                if er_nr >= 2:
                    raise e
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

        # === Get Hall of fame
        best_saves.sort(key=lambda x: x[3], reverse=False)
        hof_len = 7
        hof = [
            {
                "empty": False,
                "img": "close_call",
                "title": "Not Even Close",
                "description": "Hits with lowest chain timer",
                "column": "Timer",
                "best": [best_saves[0]],
                "rest": best_saves[1:hof_len]
            }
        ]
        titles = {
            "chain_watcher": [
                "On Guard",
                "Hits done with chain timer < 2min",
                "Saves" 
            ],
            "assists":  [
                "Support",
                "War/Raid hit assists",
                "Assits"
            ],
            "attacks":  [
                "Punch Factory",
                "War/Raid hits",
                "Hits"
            ],
            "outside_attacks": [
                "Collateral Damage",
                "Outside hits",
                "Hits"
            ],
            "retaliation": [
                "Punisher",
                "Retaliation hits",
                "Hits"
            ],
            "overseas": [
                "Globetrotter",
                "War/Raid hits overseas",
                "Hits"
            ],
            "respect_leaked": [
                "Piñata",
                "Respect given to enemy faction",
                "Respect"
            ]
        }
        for key in titles.keys():
            arr = [[int(output_data[member][key]), member, output_data[member]["name"]] for member in output_data if output_data[member][key]]
            arr.sort(key=lambda x: x[0], reverse=True)
            if len(arr):
                tops = 1
                for a in arr[1:]:
                    if a[0] == arr[0][0]:
                        tops += 1
                    else:
                        break
                if tops == 1:
                    hof.append({
                        "empty": False,
                        "img": key,
                        "title": titles[key][0],
                        "description": titles[key][1],
                        "column": titles[key][2],
                        "best": [arr[0]],
                        "rest": arr[1:hof_len]
                    })
                else:
                    hof.append({
                        "empty": False,
                        "img": key,
                        "title": titles[key][0],
                        "description": titles[key][1],
                        "column": titles[key][2],
                        "best": [],
                        "rest": arr[:hof_len]
                    })
            else:
                hof.append({
                    "empty": True,
                        "img": key,
                    "title": titles[key][0],
                    "description": titles[key][1],
                    "column": titles[key][2],
                    "best": [],
                    "rest": []
                })

        arr = [
            [member, output_data[member]["name"], int(output_data[member]["attacks_below_2_ff"]), int(output_data[member]["attacks_below_2_ff"]/output_data[member]["attacks"]*100)] \
            for member in output_data if output_data[member]["attacks"] > 10]
        arr.sort(key=lambda x: x[3], reverse=True)
        arr2 = [[a[0],a[1],a[2],f"{a[3]}%"] for a in arr]
        tops = 1
        for a in arr2[1:]:
            if a[0] == arr2[0][0]:
                tops += 1
            else:
                break
        if tops == 1:
            hof2 = [{
                "title": "Tough-on-Toddlers",
                "img": "attacks_below_2_ff",
                "description": "Hits below 2 FF score",
                "columns": ["Hits", "%"],
                "columns_n": 3,
                "best": [arr2[0]],
                "rest": arr2[1:hof_len]
            }]
        else:
            hof2 = [{
                "title": "Tough-on-Toddlers",
                "img": "attacks_below_2_ff",
                "description": "Hits below 2 FF score",
                "columns": ["Hits", "%"],
                "columns_n": 3,
                "best": [],
                "rest": arr2[:hof_len]
            }]

        # === Save to htmls
        columns = list(next(iter(output_data.values())).keys())
        table = sorted(list(output_data.values()), key=lambda x: x['payout'], reverse=True)
        tables = [table]
        if len(table) > 50:
            len_table_half = len(table)//2
            tables = [table[:len_table_half], table[len_table_half:]]
        env = Environment(
            loader=FileSystemLoader(searchpath="."),   # looks in current directory
            autoescape=select_autoescape(["html", "xml"])
        )

        pwd = os.getcwd()
        os.chdir(application_path)
        template = env.get_template("util/template.html")
        html_str = template.render(
            title   = f"War agains {enemy_name} report",
            victory = did_we_won,
            rewards  = rewards,
            payout  = payout_str,
            columns = columns,
            tresholds = [hits_treshold_downgrade, hits_treshold_upgrade],
            tables  = tables,
            hof  = hof,
            hof2 = hof2
        )

        out_path = Path("table.html").resolve()
        out_path.write_text(html_str, encoding="utf-8")
        enemy_name = enemy_name.replace(" ", "_")

        os.chdir(pwd)
        weasyprint_path = os.path.join(application_path, "util", "weasyprint.exe")
        html_path = os.path.join(application_path, "table.html")
        pdf_path = os.path.join(pwd, f"payouts_{enemy_name}.pdf")
        subprocess.run(f"{weasyprint_path} {html_path} {pdf_path}", check=False)
    except Exception as e:
        error_text = traceback.format_exc()
        messagebox.showerror("Error!", error_text)

def run_main_with_animation():
    def worker():
        try:
            button.config(text="Generating")
            main()
        finally:
            # stop animation after task
            running.set(False)
            button.config(text="Generate", state="normal")

    # start animation
    running.set(True)
    button.config(state="disabled")
    animate_button()
    threading.Thread(target=worker, daemon=True).start()

def animate_button():
    if running.get():
        current = button["text"]
        if current.endswith("..."):
            button.config(text="Generating")
        else:
            button.config(text=current + ".")
        root.after(400, animate_button)  # repeat every 400ms

# Create main window
root = tk.Tk()
root.iconbitmap(os.path.join(application_path, "img", "icon.ico"))
root.title("War report generator - by Mosti")
root.geometry("360x400")
root.resizable(False, False)
style = ttk.Style()
style.theme_use("xpnative")
default_values = [
    [13421, "Enemy Faction ID", tk.IntVar],
    ["16:00:09 07/11/25", "Starting time", tk.StringVar],
    ["09:00:25 08/11/25", "Ending time", tk.StringVar],
    ["", "Api Key - Limited Access", tk.StringVar],
    [100, "Raid points factor during war in % (0-100)", tk.IntVar],
    [100, "Raid points factor after war in % (0-100)", tk.IntVar],
    [70, "Members cut in % (0-100)", tk.IntVar]
]

text_vars = []
for i, value in enumerate(default_values):
    var = value[2](value=value[0])  # set default value
    text_vars.append(var)
    ttk.Label(root, text=value[1]).pack(pady=(10 if i == 0 else 5, 0))
    entry = ttk.Entry(root, textvariable=var, width=40)
    entry.pack()

running = tk.BooleanVar(value=False)
button = ttk.Button(root, text="Generate", command=run_main_with_animation, width=15)
button.pack(pady=20)
root.mainloop()
# etrgwAdkvDZgHC8W

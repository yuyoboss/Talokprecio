import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

URL = "https://www.leskamas.com/es/vende-kamas.html"
SERVER = "Talok"
THRESHOLDS = [1.79, 1.89, 1.99]  # euros por millón
STATE_FILE = "state.json"


def get_price():
    r = requests.get(
        URL,
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
        timeout=30,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tr in soup.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 2 and cells[0].lower() == SERVER.lower():
            m = re.search(r"(\d+(?:[.,]\d+)?)", cells[1])
            if m:
                return float(m.group(1).replace(",", "."))
    raise RuntimeError(f"No encuentro la fila de {SERVER} en la tabla")


def send_telegram(text):
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text},
        timeout=30,
    )
    r.raise_for_status()


def load_state():
    try:
        with open(STATE_FILE) as f:
            alerted = json.load(f).get("alerted", [])
    except Exception:
        alerted = []
    # Compatibilidad con el formato antiguo (true/false)
    if isinstance(alerted, bool):
        alerted = [THRESHOLDS[0]] if alerted else []
    return {"alerted": alerted}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def main():
    price = get_price()
    state = load_state()
    print(f"{SERVER}: {price} EUR/M (umbrales {THRESHOLDS}, avisados={state['alerted']})")

    # Rearmar los umbrales que el precio ya ha dejado atrás por debajo
    alerted = [t for t in state["alerted"] if price > t]

    # Umbrales superados que todavía no se han avisado
    nuevos = [t for t in THRESHOLDS if price > t and t not in alerted]
    if nuevos:
        send_telegram(f"{SERVER} está a {price} €/M (supera {max(nuevos)} €/M)")
        alerted += nuevos

    state["alerted"] = sorted(alerted)
    save_state(state)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)  # GitHub te manda un email si el workflow falla



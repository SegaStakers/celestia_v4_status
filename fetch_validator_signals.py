import json
import requests
import time
from datetime import datetime, timezone

VALIDATORS_FILE = "validators.json"
README_FILE = "README.md"
TX_API = "http://5.9.93.178:1317/cosmos/tx/v1beta1/txs"

def load_validators():
    with open(VALIDATORS_FILE, "r") as f:
        return json.load(f)

def get_latest_signal_version(account_address):
    params = {
        "events": [
            f"message.sender='{account_address}'",
            "tx.height>=6402739"
        ],
        "pagination.limit": 100,
        "order_by": 1,  # ascending by height
    }

    while True:
        try:
            response = requests.get(TX_API, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            break
        except Exception as e:
            print(f"[WARN] Retrying for {account_address} due to error: {e}")
            time.sleep(3)

    txs = data.get("tx_responses", [])
    if not txs:
        return "-", "-", "-"

    # Find the latest tx with MsgSignalVersion message type (highest height)
    latest_tx = None
    for tx in reversed(txs):  # reverse to start from latest
        messages = tx.get("tx", {}).get("body", {}).get("messages", [])
        for msg in messages:
            if msg.get("@type") == "/celestia.signal.v1.MsgSignalVersion":
                latest_tx = tx
                break
        if latest_tx:
            break

    if not latest_tx:
        return "-", "-", "-"

    # Extract version
    version = "-"
    for msg in latest_tx.get("tx", {}).get("body", {}).get("messages", []):
        if msg.get("@type") == "/celestia.signal.v1.MsgSignalVersion":
            version = msg.get("version", "-")

    # Extract hash and height
    txhash = latest_tx.get("txhash", "-")
    if len(txhash) > 5:
        txhash = "..." + txhash[-5:]
    height = latest_tx.get("height", "-")

    return version, txhash, height

def format_row(idx, moniker, vp, status, version, txhash, height):
    return f"| {idx} | {moniker} | {vp} | {status} | {version} | {txhash} | {height} |"

def build_markdown(validators):
    header = "| # | Moniker | VP (%) | Status | Ver | Hash | Height |\n"
    separator = "|---|---------|--------|--------|-----|------|--------|\n"
    rows = [header, separator]

    total_vp = 0.0
    idx = 1
    for v in validators:
        status = v.get("status", "").upper()
        if status not in ("BONDED", "UNBONDING"):
            continue

        version, txhash, height = get_latest_signal_version(v["account_address"])

        # Only sum VP if version == "4" (or adjust as needed)
        if version == "4":
            try:
                vp_float = float(v.get("voting_power_percent", "0"))
            except Exception:
                vp_float = 0.0
            total_vp += vp_float
            vp_percent_str = f"{vp_float * 100:.3f}"
        else:
            vp_percent_str = f"{float(v.get('voting_power_percent', '0')) * 100:.3f}"

        row = format_row(
            idx,
            v.get("moniker", "-"),
            vp_percent_str,
            status,
            version,
            txhash,
            height,
        )
        rows.append(row + "\n")
        idx += 1

    return "".join(rows), total_vp


def main():
    print("[INFO] Loading validator list...")
    validators = load_validators()

    print("[INFO] Generating report...")
    report_md, total_vp = build_markdown(validators)

    total_vp_percent = total_vp * 100

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    with open(README_FILE, "w") as f:
        f.write(f"# Celestia Validator Signal Report\n\n")
        f.write(f"Last updated: **{timestamp}**\n\n")
        f.write(f"**Sum of Voting Power (BONDED+UNBONDING): {total_vp_percent:.3f}%**\n\n")
        f.write(report_md + "\n")

    print("[INFO] Report generated and saved to README.md")
    print(f"[INFO] Total Voting Power (BONDED+UNBONDING): {total_vp_percent:.3f}%")

if __name__ == "__main__":
    main()

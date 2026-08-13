#!/usr/bin/env python3
import argparse, hashlib, json, sys, tomllib
from pathlib import Path

PLANES = ("semantics", "evaluation", "runtime", "evidence", "operations")
LEVELS = ("M0 Seed", "M1 Modeled", "M2 Admitted", "M3 Runnable", "M4 Receipted", "M5 Replayable", "M6 Enterprise")

def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()

def load(path="gym.toml"):
    with open(path, "rb") as handle:
        return tomllib.load(handle)

def validate(m):
    errors = []
    if m.get("contract_version") != "1": errors.append("contract_version must be 1")
    if m.get("gym", {}).get("mode") != "offline_simulation": errors.append("gym.mode must be offline_simulation")
    if m.get("exercise", {}).get("kind") != "offline_simulation": errors.append("exercise.kind must be offline_simulation")
    levels = m.get("maturity", {}).get("planes", {})
    for p in PLANES:
        if not isinstance(levels.get(p), int) or not 0 <= levels[p] <= 6: errors.append(f"invalid plane: {p}")
    return errors, levels

def check(m):
    errors, levels = validate(m)
    if errors:
        print(json.dumps({"standing":"BLOCKED","errors":errors}, indent=2)); return 1
    floor = min(levels[p] for p in PLANES)
    print(json.dumps({"standing":"PARTIAL_ALIVE","overall":LEVELS[floor],"planes":{p:LEVELS[levels[p]] for p in PLANES}}, indent=2, sort_keys=True)); return 0

def evaluate(m, out):
    errors, levels = validate(m)
    if errors: return check(m)
    subject = {"gym":m["gym"]["name"],"exercise":m["exercise"]["id"],"mode":m["gym"]["mode"]}
    receipt = {"schema":"gym-receipt/v1","standing":"PARTIAL_ALIVE","subject":subject,"observed":["gym.toml"],"admitted":[subject],"executed":["offline maturity evaluation"],"changed":[],"verified":["manifest shape","five-plane floor","deterministic receipt"],"inferred":[],"refused":[],"blocked":[],"unsupported":[],"overall_level":min(levels[p] for p in PLANES),"manifest_digest":digest(m),"subject_digest":digest(subject)}
    receipt["receipt_digest"] = digest(receipt)
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if out: Path(out).write_text(text)
    print(text, end=""); return 0

def replay(path):
    receipt = json.loads(Path(path).read_text()); claimed = receipt.pop("receipt_digest", None); actual = digest(receipt)
    print(json.dumps({"replay":"PASS" if claimed == actual else "FAIL","claimed":claimed,"actual":actual}, indent=2)); return 0 if claimed == actual else 1

def main():
    p = argparse.ArgumentParser(); p.add_argument("command", choices=("check","evaluate","replay")); p.add_argument("target", nargs="?", default="gym.toml"); p.add_argument("--out"); a = p.parse_args()
    return replay(a.target) if a.command == "replay" else (check(load(a.target)) if a.command == "check" else evaluate(load(a.target), a.out))

if __name__ == "__main__": sys.exit(main())

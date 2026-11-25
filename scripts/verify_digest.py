"""Validação de múltiplas datas com rede; somente prévias locais."""
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import sys
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sports_digest.collector import collect
from sports_digest.formatter import render


def main():
    config = tomllib.loads(Path("config/preferences.toml").read_text(encoding="utf-8"))
    results = []
    for raw in sys.argv[1:] or ["2026-11-22", "2026-11-25", "2026-11-28", "2026-11-29"]:
        digest = collect(date.fromisoformat(raw), config)
        Path("output").mkdir(exist_ok=True)
        Path(f"output/{raw}.json").write_text(json.dumps(asdict(digest), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        Path(f"output/{raw}.txt").write_text(render(digest, config), encoding="utf-8")
        report = {"date": raw, "events": len(digest.events), "unknown_broadcasts": sum(not e.channels for e in digest.events), "warnings": digest.warnings, "source_reports": len(digest.source_reports), "highlights": [{"game": e.home + " x " + e.away, "channels": e.channels} for e in digest.events if e.competition == "nfl" or any("São Paulo capital" in c for c in e.channels)]}
        results.append(report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    Path("output/audit/validation.json").parent.mkdir(parents=True, exist_ok=True)
    Path("output/audit/validation.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

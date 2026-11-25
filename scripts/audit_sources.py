"""Captura fontes públicas para diagnóstico local; não envia mensagens."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request

URLS = {
    "nfl_calendar": "https://futebolamericano.wiki.br/nfl/calendario/",
    "nfl_espn": "https://futebolamericano.wiki.br/nfl/onde-assistir/espn-disney-plus/",
    "guide_espn3": "https://www.guiadetv.com/canal/espn-3",
    "overdrive": "https://gameoverdrive.com.br/jogos-de-hoje/",
    "globo_sp": "https://redeglobo.globo.com/programacao/",
    "globo_sp_local": "https://redeglobo.globo.com/sao-paulo/programacao/",
    "prime_help": "https://www.primevideo.com/-/pt/help/?nodeId=TXsV81Exq70bTlr2Xw",
}
URLS.update({f"guide_espn{n}": "https://www.guiadetv.com/canal/" + ("espn" if n == 1 else f"espn-{n}") for n in range(1, 7)})


def main():
    folder = Path("output/audit")
    folder.mkdir(parents=True, exist_ok=True)
    def fetch(item):
        key, url = item
        record = {"source": key, "url": url, "checked_at": datetime.now(timezone.utc).isoformat()}
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "SportsDigest/0.1"})
            with urllib.request.urlopen(request, timeout=25) as response:
                raw = response.read().decode("utf-8")
                record.update(status=response.status, bytes=len(raw))
            (folder / f"{key}.html").write_text(raw, encoding="utf-8")
        except Exception as exc:
            record.update(status="unavailable", error=type(exc).__name__)
        return record
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(fetch, URLS.items()))
    (folder / "requests.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

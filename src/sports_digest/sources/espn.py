from datetime import datetime
from ..http import SourceError, get_json
from ..models import Event, normalize

LEAGUES = {
    "nba": "basketball/nba", "nfl": "football/nfl",
    "brasileirao_serie_a": "soccer/bra.1", "copa_do_brasil": "soccer/bra.copa_do_brazil",
    "libertadores": "soccer/conmebol.libertadores", "sulamericana": "soccer/conmebol.sudamericana",
    "paulista_a1": "soccer/bra.camp.paulista", "champions_league": "soccer/uefa.champions",
    "la_liga": "soccer/esp.1", "premier_league": "soccer/eng.1",
}


def parse(data, key, url):
    if not isinstance(data, dict) or "events" not in data or not data.get("leagues"):
        raise SourceError("Formato da ESPN mudou")
    expected = LEAGUES[key].split("/")[-1]
    if data["leagues"][0].get("slug") != expected:
        raise SourceError("Competição divergente na ESPN")
    events, warnings = [], []
    if len(data["events"]) >= 100:
        warnings.append("ESPN: limite de eventos atingido; cobertura pode estar incompleta")
    for raw in data["events"]:
        try:
            comp = raw["competitions"][0]
            teams = {t["homeAway"]: t["team"]["displayName"] for t in comp["competitors"]}
            status = comp.get("status", raw.get("status", {})).get("type", {}).get("name", "")
            # 'broadcasts' sem região pode conter canais dos EUA. Somente BR explícito.
            channels = [b["media"]["shortName"] for b in comp.get("geoBroadcasts", []) if b.get("region", "").lower() == "br"]
            open_tv = {"globo", "tv globo", "sbt", "record", "record tv", "band", "redetv", "tv cultura", "xsports"}
            channels = [name + " (praça de São Paulo a confirmar)" if normalize(name) in open_tv else name for name in channels]
            phase = " ".join(str(n.get("headline", "")) for n in comp.get("notes", []))
            events.append(Event(
                id="espn:" + raw["id"], competition=key, home=teams["home"], away=teams["away"],
                start=datetime.fromisoformat(raw["date"].replace("Z", "+00:00")),
                season=raw.get("season", {}).get("slug", ""), phase=phase,
                status=status, time_confirmed=comp.get("timeValid", True) and not comp.get("status", {}).get("isTBDFlex", False),
                channels=channels, sources=[url],
            ))
        except (KeyError, ValueError, TypeError, IndexError):
            warnings.append("ESPN: evento com dados incompletos; cobertura pode estar incompleta")
    return events, warnings


def fetch(key, day):
    url = f"https://site.api.espn.com/apis/site/v2/sports/{LEAGUES[key]}/scoreboard?dates={day:%Y%m%d}&limit=100&region=br&lang=pt"
    return parse(get_json(url), key, url)

"""Lê somente os dados JSON públicos incorporados na agenda do ge."""
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from ..http import SourceError, get_text
from ..models import Event, normalize

URL = "https://ge.globo.com/agenda/"
NAMES = {
    "nba": "nba", "nfl": "nfl", "campeonato brasileiro": "brasileirao_serie_a",
    "brasileirao serie a": "brasileirao_serie_a", "copa do brasil": "copa_do_brasil",
    "libertadores": "libertadores", "taca libertadores": "libertadores",
    "copa sul americana": "sulamericana", "sul americana": "sulamericana",
    "campeonato paulista": "paulista_a1", "paulista": "paulista_a1",
    "champions league": "champions_league", "liga dos campeoes": "champions_league",
    "campeonato espanhol": "la_liga", "la liga": "la_liga",
    "campeonato ingles": "premier_league", "premier league": "premier_league",
}
# Lista de serviços que realmente exibem vídeo; exclui Cartola e links de cobertura textual.
CHANNELS = {normalize(n) for n in [
    "Premiere", "SporTV", "SporTV 2", "SporTV 3", "sportv2", "sportv3", "Globoplay",
    "Disney+", "Disney+ Premium", "ESPN", "ESPN 2", "ESPN 3", "ESPN 4", "ESPN 5", "ESPN 6",
    "HBO Max", "Max", "TNT", "Space", "Prime Video", "Amazon Prime Video", "Paramount+",
    "CazéTV", "Cazé TV", "Ge TV", "getv", "YouTube", "NBA League Pass", "NFL Game Pass", "DAZN",
    "TV Globo", "Globo", "SBT", "Record", "Record TV", "Band", "RedeTV!", "TV Cultura", "Xsports",
]}
OPEN_TV = {normalize(n) for n in ["TV Globo", "Globo", "SBT", "Record", "Record TV", "Band", "RedeTV!", "TV Cultura", "Xsports"]}


def parse(html):
    marker = html.find("window.dataSportsSchedule")
    if marker < 0:
        raise SourceError("Dados da agenda do ge não encontrados")
    decoder = json.JSONDecoder()
    results, dates, warnings = [], set(), []
    for section in ("sport", "multisport"):
        match = re.search(r"\b" + section + r":\s*", html[marker:])
        if not match:
            raise SourceError("Estrutura da agenda do ge mudou")
        try:
            days, _ = decoder.raw_decode(html[marker + match.end():])
        except ValueError:
            raise SourceError("JSON da agenda do ge inválido") from None
        dates.update(days)
        for day in days.values():
            blocks = [day] if section == "sport" else day.get("multisportTabAgenda", [])
            for block in blocks:
                for agenda in block.get("championshipsAgenda", []):
                    key = NAMES.get(normalize(agenda.get("championship", {}).get("name", "")))
                    if not key:
                        continue
                    for state in ("future", "now", "past"):
                        for raw in agenda.get(state, []):
                            try:
                                m = raw["match"]
                                channels = []
                                for b in m.get("liveWatchSources") or []:
                                    name = b.get("name", "")
                                    if normalize(name) in CHANNELS:
                                        if normalize(name) in OPEN_TV:
                                            name += " (praça de São Paulo a confirmar)"
                                        channels.append(name)
                                phase = (m.get("phase") or {}).get("name", "")
                                season = ""
                                if "pre temporada" in normalize(phase):
                                    season = "pre-season"
                                elif normalize(phase) == "temporada regular":
                                    season = "regular-season"
                                elif any(p in normalize(phase) for p in ("playoff", "final", "wild card", "super bowl", "play in")):
                                    season = "playoffs"
                                url = (m.get("transmission") or {}).get("url") or URL
                                results.append(Event(
                                    id="ge:" + str(m["id"]), competition=key,
                                    home=m["firstContestant"]["popularName"], away=m["secondContestant"]["popularName"],
                                    start=datetime.fromisoformat(m["startDate"] + "T" + m["startHour"]).replace(tzinfo=ZoneInfo("America/Sao_Paulo")),
                                    phase=phase, season=season, channels=channels, sources=[url],
                                ))
                            except (KeyError, ValueError, TypeError):
                                warnings.append(f"ge: evento incompleto em {key}")
    return results, dates, warnings


def fetch():
    return parse(get_text(URL))

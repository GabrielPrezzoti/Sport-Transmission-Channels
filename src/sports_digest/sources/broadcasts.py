"""Fontes editoriais brasileiras: complementam canais, nunca inventam jogos."""
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import re
import json
from html import unescape
from zoneinfo import ZoneInfo
from ..http import SourceError, get_text
from ..models import team_key, normalize

TZ = ZoneInfo("America/Sao_Paulo")
OVERDRIVE = "https://gameoverdrive.com.br/jogos-de-hoje/"


class Node:
    def __init__(self, tag="", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return "".join(child if isinstance(child, str) else child.text() for child in self.children)

    def find(self, cls):
        found = [self] if cls in self.attrs.get("class", "").split() else []
        for child in self.children:
            if isinstance(child, Node):
                found.extend(child.find(cls))
        return found

    def tags(self, tag):
        found = [self] if self.tag == tag else []
        for child in self.children:
            if isinstance(child, Node):
                found.extend(child.tags(tag))
        return found


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)
        if tag == "br":
            node.children.append("\n")

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


@dataclass
class Listing:
    competition: str
    teams: tuple
    start: datetime
    channels: list[str]
    url: str
    source: str
    updated_at: str | None = None
    end: datetime | None = None


def modified_at(html):
    match = re.search(r'"dateModified"\s*:\s*"([^"]+)"', html)
    return match[1] if match else None


def channels(text):
    result = []
    for part in re.split(r"[·•,;/]|\s+e\s+", text):
        name = " ".join(part.split()).strip(" .")
        if re.fullmatch(r"ESPN(?:\s*[2-6])?", name, re.I):
            number = re.search(r"[2-6]", name)
            result.append("ESPN" + (" " + number[0] if number else ""))
        else:
            known = {"disney": "Disney+", "disney premium": "Disney+ Premium", "prime video": "Prime Video", "amazon prime video": "Prime Video", "nba league pass": "NBA League Pass (assinatura adicional)", "league pass": "NBA League Pass (assinatura adicional)", "nfl game pass": "NFL Game Pass (DAZN; assinatura adicional)", "netflix": "Netflix", "sportv": "SporTV", "sportv 2": "SporTV 2", "sportv2": "SporTV 2", "sportv 3": "SporTV 3", "sportv3": "SporTV 3", "ge tv": "ge tv"}
            if normalize(name) in known:
                result.append(known[normalize(name)])
    if "nfl game pass no dazn" in normalize(text):
        result.append("NFL Game Pass (DAZN; assinatura adicional)")
    extras = {"hbo max": "HBO Max", "max": "HBO Max", "tnt": "TNT", "space": "Space", "premiere": "Premiere", "globoplay": "Globoplay", "paramount": "Paramount+", "cazetv": "CazéTV", "caze tv": "CazéTV", "youtube": "YouTube", "globo": "Globo (praça de São Paulo a confirmar)", "tv globo": "TV Globo (praça de São Paulo a confirmar)", "sbt": "SBT (praça de São Paulo a confirmar)", "record": "Record (praça de São Paulo a confirmar)", "band": "Band (praça de São Paulo a confirmar)"}
    for part in re.split(r"[·•,;/]|\s+e\s+", text):
        if normalize(part) in extras:
            result.append(extras[normalize(part)])
    return sorted(set(result))


def parse_overdrive(html):
    root = Tree(html).root
    blocks = root.find("od-games__comp")
    if not blocks:
        raise SourceError("Estrutura da agenda Overdrive não encontrada")
    found, notes = [], []
    for block in blocks:
        league = block.find("od-games__league")
        label = normalize(league[0].text()) if league else ""
        key = competition_key(label)
        if not key:
            continue
        for item in block.find("od-game"):
            try:
                title = item.find("od-game__name")[0]
                teams = re.split(r"\s+[x×]\s+", title.text().strip())
                if len(teams) != 2:
                    raise ValueError("Confronto inválido")
                time_node = item.find("od-game__time")[0]
                start = datetime.fromisoformat(time_node.attrs["datetime"].replace("Z", "+00:00"))
                if start.tzinfo is None:
                    raise ValueError("Horário sem fuso")
                tv = item.find("od-game__tv")[0].text().replace("Onde assistir:", "")
                parsed = channels(tv)
                if not parsed and tv.strip():
                    notes.append(f"Overdrive: canal não reconhecido em {title.text().strip()}")
                found.append(Listing(key, tuple(sorted(team_key(t) for t in teams)), start, parsed, title.attrs.get("href", OVERDRIVE), "Overdrive", modified_at(html)))
            except (IndexError, KeyError, ValueError):
                notes.append("Overdrive: partida com transmissão incompleta")
    return found, notes


def fetch_overdrive(day):
    return parse_overdrive(get_text(OVERDRIVE))


def hoops_url(day, prime=False):
    year = day.year if day.month >= 7 else day.year - 1
    suffix = "do-prime-video" if prime else "da-espn-e-disney"
    return f"https://hoopsbrasil.com.br/nba-{year}-{str(year + 1)[-2:]}-calendario-de-transmissoes-{suffix}/"


def parse_hoops(html, url):
    # Datas são da rodada: 0h/1h pertencem ao dia civil seguinte.
    root = Tree(html).root
    nodes = root.find("hb-post__texto") or root.find("entry-content")
    if not nodes:
        raise SourceError("Calendário do Hoops Brasil não encontrado")
    text = "\n".join(p.text() for p in nodes[0].tags("p"))
    found, current = [], None
    for line in text.splitlines():
        match = re.search(r"\b(\d{2}/\d{2}/\d{2,4})\b", line)
        if match:
            raw = match[1]
            current = datetime.strptime(raw, "%d/%m/%Y" if len(raw) == 10 else "%d/%m/%y").date()
            continue
        match = re.fullmatch(r"\s*(.+?)\s+[x×]\s+(.+?)\s*[–—-]\s*(\d{1,2})h(\d{2})?\s*\(([^)]+)\)\s*", line)
        if not current or not match:
            continue
        home, away, hour, minute, tv = match.groups()
        hour = int(hour)
        start = datetime.combine(current, datetime.min.time(), TZ).replace(hour=hour, minute=int(minute or 0))
        if hour < 9:
            start += timedelta(days=1)
        found.append(Listing("nba", tuple(sorted((team_key(home), team_key(away)))), start, channels(tv), url, "Hoops Brasil", modified_at(html)))
    if not found:
        raise SourceError("Calendário sem partidas reconhecidas no Hoops Brasil")
    return found, []


def fetch_hoops(day, prime=False):
    url = hoops_url(day, prime)
    return parse_hoops(get_text(url), url)


def enrich(events, listings):
    warnings = []
    checked = datetime.now(timezone.utc).isoformat()
    for listing in listings:
        candidates = [e for e in events if e.competition == listing.competition and e.match_key[1] == listing.teams and abs((e.start - listing.start).total_seconds()) < 86400]
        if len(candidates) != 1:
            continue
        event = candidates[0]
        regional_interval = listing.source == "Globo SP oficial" and listing.end and listing.start <= event.start < listing.end
        if not regional_interval and abs((event.start - listing.start).total_seconds()) > 900:
            warnings.append(f"{listing.source}: horário divergente em {event.home} × {event.away}; canais não incorporados")
            continue
        for channel in listing.channels:
            event.channels.append(channel)
            event.broadcast_evidence.append({"channel": channel, "source": listing.source, "url": listing.url, "checked_at": checked, "updated_at": listing.updated_at, "country": "BR", "access": "additional_subscription" if "assinatura adicional" in channel else "prime_included" if channel == "Prime Video" else "unspecified"})
        if listing.channels:
            event.sources.append(listing.url)
    for event in events:
        canonical = {"prime video": "Prime Video", "amazon prime video": "Prime Video", "disney": "Disney+", "disney premium": "Disney+ Premium"}
        event.channels = sorted({canonical.get(normalize(c), c) for c in event.channels})
        # Refinar a indicação genérica quando há canal/plano específico.
        if "Disney+ Premium" in event.channels and "Disney+" in event.channels:
            event.channels.remove("Disney+")
        if "ESPN" in event.channels and any(re.fullmatch(r"ESPN [2-6]", c) for c in event.channels):
            event.channels.remove("ESPN")
        if "NBA League Pass (assinatura adicional)" in event.channels and "NBA League Pass" in event.channels:
            event.channels.remove("NBA League Pass")
        event.sources = sorted(set(event.sources))
        if "Globo (São Paulo capital)" in event.channels:
            event.channels = [c for c in event.channels if c not in ("Globo (praça de São Paulo a confirmar)", "TV Globo (praça de São Paulo a confirmar)")]
        numbered = {}
        for evidence in event.broadcast_evidence:
            if re.fullmatch(r"ESPN [2-6]", evidence["channel"]):
                numbered.setdefault(evidence["source"], set()).add(evidence["channel"])
        values = list(numbered.values())
        if len(values) > 1 and any(value != values[0] for value in values[1:]):
            disputed = set.union(*values)
            event.channels = [c for c in event.channels if c not in disputed]
            event.channels.append("ESPN (número a confirmar)")
            warnings.append(f"{event.home} × {event.away}: canais ESPN divergentes; verificar fontes")
    return warnings


def competition_key(label):
    label = normalize(label)
    if any(word in label for word in ("feminino", "feminina", "sub 20", "sub 17", "amistoso", "serie b", "serie c", "serie d")):
        return None
    from .ge import NAMES
    aliases = dict(NAMES, **{"brasileirao": "brasileirao_serie_a", "brasileiro serie a": "brasileirao_serie_a"})
    for name in sorted(aliases, key=len, reverse=True):
        if label == name or label.startswith(name + " "):
            return aliases[name]
    return None


def parse_fawiki(html, url):
    cards = Tree(html).root.find("schedule-card")
    if not cards:
        raise SourceError("Calendário FA.wiki não reconhecido")
    found, notes = [], []
    for card in cards:
        try:
            names = [t.tags("strong")[0].text() for t in card.find("schedule-team")]
            if len(names) != 2:
                raise ValueError()
            start = datetime.fromisoformat(card.tags("time")[0].attrs["datetime"])
            if not start.tzinfo:
                raise ValueError()
            tv = card.find("schedule-broadcast-links")[0].text()
            found.append(Listing("nfl", tuple(sorted(team_key(t) for t in names)), start, channels(tv), url + "#" + card.attrs.get("id", ""), "FA.wiki"))
        except (KeyError, IndexError, ValueError):
            notes.append("FA.wiki: partida sem data, times ou canais reconhecidos")
    return found, sorted(set(notes))


def fetch_fawiki(day):
    found, notes = [], []
    for url in ("https://futebolamericano.wiki.br/nfl/calendario/", "https://futebolamericano.wiki.br/nfl/onde-assistir/espn-disney-plus/"):
        try:
            items, warnings = parse_fawiki(get_text(url), url)
            found.extend(items); notes.extend(warnings)
        except Exception:
            notes.append("FA.wiki: uma das páginas indisponível; cobertura parcial")
    return found, notes


def parse_guide(html, channel, url):
    root = Tree(html).root
    records = []
    for script in root.tags("script"):
        if script.attrs.get("type") != "application/ld+json":
            continue
        try:
            data = json.loads(script.text())
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "TelevisionChannel":
            records.extend(data.get("broadcastEvent", []))
    if not records:
        raise SourceError("Grade estruturada não reconhecida")
    found = []
    for raw in records:
        match = re.fullmatch(r"(NBA|NFL)\s*:\s*(.+?)\s+[x×]\s+(.+?)(?:\s+-\s+Ao Vivo)?", raw.get("name", ""), re.I)
        if match:
            sport, first, second = match.groups()
            start = datetime.fromisoformat(raw["startDate"])
            if start.tzinfo:
                found.append(Listing(sport.lower(), tuple(sorted((team_key(first), team_key(second)))), start, [channel], url, "Guia de TV"))
    return found, []


def fetch_guide(day):
    def fetch(number):
        channel = "ESPN" if number == 1 else f"ESPN {number}"
        url = "https://www.guiadetv.com/canal/" + ("espn" if number == 1 else f"espn-{number}")
        try:
            return parse_guide(get_text(url), channel, url)
        except Exception:
            return [], [f"Guia de TV: grade {channel} indisponível"]
    found, notes = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for items, warnings in pool.map(fetch, range(1, 7)):
            found.extend(items); notes.extend(warnings)
    return found, notes


GLOBO_SP = "https://redeglobo.globo.com/sao-paulo/programacao/"


def parse_globo_sp(html):
    match = re.search(r'<main[^>]*data-props="([^"]+)"', html)
    if not match:
        raise SourceError("Grade regional Globo SP não encontrada")
    data = json.loads(unescape(match[1]))["context"]["gridData"]["data"]
    if data.get("channelCode") != "GGP1":
        raise SourceError("Identidade regional Globo SP divergente")
    found = []
    for day in data["output"]:
        for slot in day["slots"]:
            name = slot.get("name", "")
            parts = re.fullmatch(r"(.+?)\s+-\s+(.+?)\s+[x×]\s+(.+)", name)
            if not parts:
                continue
            label, first, second = parts.groups()
            key = competition_key(label.replace("Final da ", ""))
            if not key:
                continue
            start = datetime.fromisoformat(slot["scheduledDate"])
            h, m, s = map(int, slot["duration"].split(":"))
            found.append(Listing(key, tuple(sorted((team_key(first), team_key(second)))), start, ["Globo (São Paulo capital)"], GLOBO_SP, "Globo SP oficial", data.get("modified"), start + timedelta(hours=h, minutes=m, seconds=s)))
    return found, []


def fetch_globo_sp(day):
    return parse_globo_sp(get_text(GLOBO_SP))


def parse_tvinside(html, channel, day, url):
    # Cada registro tem data/hora completas. Ignorar reprises e programas genéricos.
    records = re.split(r'<div\b[^>]*\bdti="', html)[1:]
    if not records:
        raise SourceError("Grade do TV Inside não reconhecida")
    listings = []
    for record in records:
        try:
            raw = record.split('"', 1)[0]
            start = datetime.fromisoformat(raw).replace(tzinfo=TZ)
            if start.date() not in (day, day + timedelta(days=1)):
                continue
            title = re.search(r'<span class=["\']?titulo["\']?>(.*?)</span>', record, re.S)
            if not title:
                continue
            text = Tree(title[1]).root.text().strip()
            match = re.fullmatch(r'(NBA|NFL)\s*:\s*(.+?)\s+[x×]\s+(.+)', text, re.I)
            if not match:
                continue
            sport, first, second = match.groups()
            listings.append(Listing(sport.lower(), tuple(sorted((team_key(first), team_key(second)))), start, [channel], url, "TV Inside"))
        except ValueError:
            continue
    return listings


def fetch_tvinside(day):
    weekday = ("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo")[day.weekday()]
    def fetch_channel(number):
        slug = "espn" if number == 1 else f"espn_{number}"
        channel = "ESPN" if number == 1 else f"ESPN {number}"
        url = f"https://tvinside.com.br/programacao_tv/{slug}/{weekday}"
        try:
            return parse_tvinside(get_text(url), channel, day, url), []
        except Exception:
            return [], [f"TV Inside: grade de {channel} indisponível"]
    listings, notes = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        # O índice ainda usa nomes legados para outros canais (Brasil/Extra/
        # International). Só ESPN 2 teve a identidade atual validada nesta fonte.
        for found, errors in pool.map(fetch_channel, [2]):
            listings.extend(found)
            notes.extend(errors)
    return listings, notes

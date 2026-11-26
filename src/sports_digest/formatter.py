from zoneinfo import ZoneInfo
from datetime import timedelta
from html import escape
from html.parser import HTMLParser
from .models import normalize


def display_channels(channels):
    aliases = {"sportv": "SporTV", "sportv2": "SporTV 2", "sportv 2": "SporTV 2", "sportv3": "SporTV 3", "sportv 3": "SporTV 3", "ge tv": "ge tv", "getv": "ge tv", "globoplay": "Globoplay", "prime video": "Prime Video"}
    names = {aliases.get(normalize(c), c) for c in channels}
    streams = ("Globoplay", "Prime Video", "Disney+", "HBO Max", "Netflix", "Paramount+", "ge tv")
    return sorted(names, key=lambda c: ("assinatura adicional" in c, c.startswith(streams), c))


def render(digest, config):
    tz = ZoneInfo(config["timezone"])
    last_minute = digest.end - timedelta(minutes=1)
    blocks = [f"🏟️ <b>Agenda esportiva · {digest.start:%d/%m/%Y}</b>\nHorários de Brasília\n{digest.start:%d/%m, %Hh%M} → {last_minute:%d/%m, %Hh%M}"]
    sports = [("football", "⚽ Futebol"), ("basketball", "🏀 Basquete"), ("american_football", "🏈 Futebol americano")]
    if not digest.events:
        blocks.append("Não haverá jogos na sua seleção nesta janela." if not digest.warnings else "Nenhum jogo confirmado na seleção para esta janela.")
    for sport, title in sports:
        competitions = [c for c in config["competitions"] if c["sport"] == sport and any(e.competition == c["key"] for e in digest.events)]
        if not competitions:
            continue
        if sport == "basketball":
            title = "🏀 NBA"
        elif sport == "american_football":
            title = "🏈 NFL"
        blocks.append(f"<b>{escape(title)}</b>")
        for comp in competitions:
            if sport == "football":
                blocks.append(f"<i>{escape(comp['name'])}</i>")
            for event in (e for e in digest.events if e.competition == comp["key"]):
                local = event.start.astimezone(tz)
                when = local.strftime("%Hh%M")
                if local.date() != digest.start.date():
                    when += local.strftime(" — %d/%m/%Y")
                broadcast = " · ".join(display_channels(event.channels)) or config["broadcasts"]["unknown_label"]
                blocks.append(f"<b>{escape(event.home)} × {escape(event.away)}</b>\n{when}\n📺 {escape(broadcast)}")
    blocks.append("<i>Programação sujeita a alterações.</i>")
    return "\n\n".join(blocks)


def split_messages(text, limit=3900):
    # Cada bloco gerado por render é HTML completo; preservar confronto e canais.
    def size(s):
        return len(s.encode("utf-16-le")) // 2
    parts, current = [], ""
    for block in text.split("\n\n"):
        if size(block) > limit:
            if current:
                parts.append(current); current = ""
            parser = InlineSplitter(limit)
            parser.feed(block)
            parser.finish()
            parts.extend(parser.parts)
            continue
        candidate = current + "\n\n" + block if current else block
        if size(candidate) > limit:
            parts.append(current)
            current = block
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


class InlineSplitter(HTMLParser):
    """Protege tags e entidades até quando um único bloco excede o limite."""
    def __init__(self, limit):
        super().__init__(convert_charrefs=True)
        self.limit, self.parts, self.tags, self.current = limit, [], [], ""

    def closing(self):
        return "".join(f"</{tag}>" for tag in reversed(self.tags))

    def handle_starttag(self, tag, attrs):
        if tag not in ("b", "i"):
            raise ValueError("Tag de mensagem não suportada")
        projected = self.current + f"<{tag}></{tag}>" + self.closing()
        if len(projected.encode("utf-16-le")) // 2 > self.limit:
            self.parts.append(self.current + self.closing())
            self.current = "".join(f"<{open_tag}>" for open_tag in self.tags)
        self.tags.append(tag)
        self.current += f"<{tag}>"

    def handle_endtag(self, tag):
        if not self.tags or self.tags[-1] != tag:
            raise ValueError("HTML de mensagem inválido")
        self.tags.pop()
        self.current += f"</{tag}>"

    def handle_data(self, data):
        for char in data:
            encoded = escape(char)
            if len((self.current + encoded + self.closing()).encode("utf-16-le")) // 2 > self.limit:
                self.parts.append(self.current + self.closing())
                self.current = "".join(f"<{tag}>" for tag in self.tags)
            self.current += encoded

    def finish(self):
        if self.tags:
            raise ValueError("HTML de mensagem incompleto")
        if self.current:
            self.parts.append(self.current)

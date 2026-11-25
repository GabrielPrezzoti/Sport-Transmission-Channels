from zoneinfo import ZoneInfo


def render(digest, config):
    tz = ZoneInfo(config["timezone"])
    lines = [f"🏟️ Agenda esportiva — {digest.start:%d/%m/%Y}", "Horários de Brasília • Transmissões no Brasil / São Paulo", f"Jogos de {digest.start:%d/%m %H:%M} até {digest.end:%d/%m} às 8h59"]
    sports = [("football", "⚽ Futebol"), ("basketball", "🏀 Basquete"), ("american_football", "🏈 Futebol americano")]
    if not digest.events:
        lines += ["", "Não haverá jogos na sua seleção nesta janela." if not digest.warnings else "Nenhum jogo confirmado na seleção. A consulta ficou incompleta; confira os avisos abaixo."]
    for sport, title in sports:
        competitions = [c for c in config["competitions"] if c["sport"] == sport and any(e.competition == c["key"] for e in digest.events)]
        if not competitions:
            continue
        lines += ["", title]
        for comp in competitions:
            lines += ["", comp["name"]]
            for event in (e for e in digest.events if e.competition == comp["key"]):
                local = event.start.astimezone(tz)
                when = local.strftime("%Hh%M")
                if local.date() != digest.start.date():
                    when += local.strftime(" — %d/%m/%Y")
                lines += [f"{when} • {event.home} × {event.away}", "📺 " + (", ".join(event.channels) or config["broadcasts"]["unknown_label"])]
    if digest.warnings:
        lines += ["", "⚠️ Consultas e dados incompletos:"] + ["• " + w for w in digest.warnings]
    lines += ["", "Fontes consultadas: ESPN, ge, Overdrive, Hoops Brasil, TV Inside, FA.wiki, Guia de TV e Globo SP. Grades sujeitas a alteração; ausência de canal não significa ausência de transmissão."]
    return "\n".join(lines)


def split_messages(text, limit=3900):
    # Margem para o limite de 4096; contar UTF-16 também protege emojis.
    def size(s):
        return len(s.encode("utf-16-le")) // 2
    parts, current = [], ""
    for line in text.splitlines(keepends=True):
        while size(line) > limit:
            if current:
                parts.append(current.rstrip()); current = ""
            cut = limit
            while size(line[:cut]) > limit:
                cut -= 1
            parts.append(line[:cut]); line = line[cut:]
        if size(current + line) > limit:
            parts.append(current.rstrip()); current = ""
        current += line
    if current.strip():
        parts.append(current.rstrip())
    return parts

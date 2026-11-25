import re
from .models import normalize, team_key


def selection(event, config):
    """Retorna (incluir, motivo de incerteza). Fase desconhecida nunca vira fase aprovada."""
    teams = {team_key(event.home), team_key(event.away)}
    allowed = {team_key(t) for t in config.get("teams", [])}
    mode = config["selection"]
    if mode == "at_least_one_team_in_list" and not teams & allowed:
        return False, ""
    if mode == "both_teams_in_list" and not teams <= allowed:
        return False, ""
    if config.get("allowed_seasons"):
        description = normalize(event.phase + " " + event.home + " " + event.away)
        if any(label in description for label in ("all star", "pro bowl", "rising stars", "pre temporada", "preseason")):
            return False, ""
        if event.season not in config["allowed_seasons"]:
            known_excluded = ("pre-season", "preseason", "all-star", "off-season", "in-season-tournament")
            return False, "" if event.season in known_excluded else "fase da temporada não identificada"
    if config.get("minimum_round"):
        phase = normalize(event.phase + " " + event.season)
        if any(p in phase for p in ("oitavas", "quartas", "semifinal", "semi final", "round of 16", "quarter", "semi final", "semifinal")) or phase in ("final", "finals"):
            return True, ""
        # 'final' isolado, sem confundir com 'primeira fase' ou 'qualifying final'.
        if re.search(r"\b(final|finals)\b", phase) and not any(p in phase for p in ("qualif", "prelim")):
            return True, ""
        match = re.search(r"(?:round|fase)\s*(\d+)|(\d+)\s*(?:a |th |st |nd |rd )?(?:fase|round)", phase)
        if match:
            return int(match.group(1) or match.group(2)) >= config["minimum_round"], ""
        # Slugs ESPN como 'fifth-round'.
        for number, word in enumerate(("first", "second", "third", "fourth", "fifth", "sixth"), 1):
            if word + " round" in phase:
                return number >= config["minimum_round"], ""
        return False, "fase da Copa do Brasil não identificada"
    if config.get("exclude_qualifying"):
        phase = normalize(event.season or event.phase)
        if any(p in phase for p in ("qualif", "prelim", "acesso")):
            return False, ""
        if "playoff" in phase or "play off" in phase:
            # Playoffs de fevereiro entram; os playoffs de acesso de agosto não.
            if "knockout" in phase or "eliminatoria" in phase:
                return True, ""
            return False, "playoff sem identificação de acesso ou mata-mata"
        if any(p in phase for p in ("league phase", "group", "primeira fase", "fase de liga", "oitavas", "quartas", "semi", "final", "round of 16", "quarter", "knockout")):
            return True, ""
        return False, "fase da Champions não identificada"
    return True, ""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from .sources import espn, ge, broadcasts
from .filters import selection


@dataclass
class Digest:
    events: list
    warnings: list[str]
    start: datetime
    end: datetime
    source_reports: list[dict] = field(default_factory=list)


def window(day, config):
    start = datetime.combine(day, time(config["delivery"]["hour"]), ZoneInfo(config["timezone"]))
    return start, start + timedelta(hours=config["delivery"]["window_hours"])


def collect(day, config):
    start, end = window(day, config)
    configs = {c["key"]: c for c in config["competitions"]}
    warnings, events, ge_events = [], [], []
    listings = []
    reports = []
    jobs = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs[pool.submit(ge.fetch)] = ("ge", None, None)
        jobs[pool.submit(broadcasts.fetch_overdrive, day)] = ("Overdrive", None, None)
        jobs[pool.submit(broadcasts.fetch_hoops, day)] = ("Hoops Brasil ESPN", None, None)
        jobs[pool.submit(broadcasts.fetch_hoops, day, True)] = ("Hoops Brasil Prime Video", None, None)
        jobs[pool.submit(broadcasts.fetch_tvinside, day)] = ("TV Inside", None, None)
        jobs[pool.submit(broadcasts.fetch_fawiki, day)] = ("FA.wiki", None, None)
        jobs[pool.submit(broadcasts.fetch_guide, day)] = ("Guia de TV", None, None)
        jobs[pool.submit(broadcasts.fetch_globo_sp, day)] = ("Globo SP oficial", None, None)
        for key in configs:
            for date in (day, day + timedelta(days=1)):
                jobs[pool.submit(espn.fetch, key, date)] = ("ESPN", key, date)
        for future in as_completed(jobs):
            source, key, date = jobs[future]
            report = {"source": source, "competition": key, "query_date": date.isoformat() if date else None, "checked_at": datetime.now(timezone.utc).isoformat(), "updated_at": None, "coverage_complete": False, "coverage_scope": "fixtures" if key else "broadcasts"}
            try:
                result = future.result()
                if source in ("Overdrive", "Hoops Brasil ESPN", "Hoops Brasil Prime Video", "TV Inside", "FA.wiki", "Guia de TV", "Globo SP oficial"):
                    found, notes = result
                    listings.extend(found)
                    warnings.extend(notes)
                    report.update(status="partial" if notes else "parsed", observed_dates=sorted({item.start.astimezone(start.tzinfo).date().isoformat() for item in found}), listings=len(found), window_listings=sum(start <= item.start < end for item in found), coverage_basis="observed_listings_only", updated_at=max((item.updated_at for item in found if item.updated_at), default=None))
                    if not any(start <= item.start < end for item in found):
                        report["status"] = "no_listings_in_window"
                elif source == "ge":
                    ge_events, dates, notes = result
                    warnings.extend(notes)
                    report.update(status="partial" if notes else "parsed", observed_dates=sorted(dates), coverage_basis="page_dates", listings=len(ge_events))
                    for required in (day, day + timedelta(days=1)):
                        if required.isoformat() not in dates:
                            warnings.append(f"ge: sem cobertura para {required:%d/%m/%Y}; transmissões podem estar incompletas")
                else:
                    found, notes = result
                    events.extend(found)
                    warnings.extend(f"{configs[key]['name']} ({date:%d/%m}): {n}" for n in notes)
                    report.update(status="partial" if notes else "parsed", observed_dates=[date.isoformat()], coverage_basis="explicit_date_query", listings=len(found), coverage_complete=not notes)
            except Exception as exc:
                report["status"] = "unavailable_or_schema_changed"
                report["error_type"] = type(exc).__name__
                # Não registrar respostas/URLs que futuramente possam conter credenciais.
                label = configs[key]["name"] if key else "todas as competições / transmissões"
                suffix = f" em {date:%d/%m}" if date else ""
                warnings.append(f"{source}: consulta indisponível para {label}{suffix}; cobertura incompleta")
            dates = report.get("observed_dates", [])
            report["observed_from"] = min(dates, default=None)
            report["observed_to"] = max(dates, default=None)
            report["dates_are_contiguous"] = False
            reports.append(report)
    # ESPN é a referência de horário. ge complementa fase, transmissão e jogos ausentes.
    merged = {}
    for event in events:
        merged[event.id] = event
    events = list(merged.values())
    for event in events:
        event.broadcast_evidence = [{"channel": channel, "source": "ESPN", "url": event.sources[0], "country": "BR", "checked_at": datetime.now(timezone.utc).isoformat(), "updated_at": None} for channel in event.channels if event.sources]
    for extra in ge_events:
        if extra.competition not in configs or not start <= extra.start < end:
            continue
        extra.broadcast_evidence = [{"channel": channel, "source": "ge", "url": extra.sources[0], "country": "BR", "checked_at": datetime.now(timezone.utc).isoformat(), "updated_at": None} for channel in extra.channels if extra.sources]
        candidates = [e for e in events if e.match_key == extra.match_key and abs((e.start - extra.start).total_seconds()) < 86400]
        if len(candidates) == 1:
            event = candidates[0]
            if abs((event.start - extra.start).total_seconds()) > 900:
                warnings.append(f"{configs[event.competition]['name']}: divergência de horário em {event.home} × {event.away}; conferir fonte")
                # Não transferir canais entre horários divergentes.
                continue
            event.channels = sorted(set(event.channels + extra.channels))
            event.broadcast_evidence.extend(extra.broadcast_evidence)
            event.sources = sorted(set(event.sources + extra.sources))
            event.phase = extra.phase or event.phase
            event.season = event.season or extra.season
        elif not candidates:
            events.append(extra)
    events = [e for e in events if start <= e.start < end]
    warnings.extend(broadcasts.enrich(events, listings))
    for listing in listings:
        if start <= listing.start < end and not any(e.match_key == (listing.competition, listing.teams) for e in events):
            warnings.append(f"{listing.source}: transmissão sem correspondência nos jogos coletados ({' × '.join(listing.teams)}); verificar nomes ou cobertura")
    selected = []
    for event in events:
        if not start <= event.start < end:
            continue
        if any(s in event.status.upper() for s in ("POSTPON", "CANCEL", "SUSPEND", "DELAY")) or not event.time_confirmed:
            warnings.append(f"{event.home} × {event.away}: horário ou realização a confirmar")
            continue
        include, reason = selection(event, configs[event.competition])
        if reason:
            warnings.append(f"{configs[event.competition]['name']}: {event.home} × {event.away} omitido — {reason}")
        if include:
            selected.append(event)
    return Digest(sorted(selected, key=lambda e: (e.start, e.competition, e.home)), sorted(set(warnings)), start, end, sorted(reports, key=lambda r: (r['source'], r['competition'] or '', r['query_date'] or '')))

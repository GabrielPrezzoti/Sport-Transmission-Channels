from datetime import date, datetime, timedelta
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from sports_digest.collector import Digest, collect, window
from sports_digest.filters import selection
from sports_digest.formatter import render, split_messages
from sports_digest.models import Event
from sports_digest.models import team_key
from sports_digest.sources import espn, ge
from sports_digest.telegram import DeliveryError, deliver

CONFIG = tomllib.loads(Path("config/preferences.toml").read_text(encoding="utf-8"))
RULES = {c["key"]: c for c in CONFIG["competitions"]}
TZ = ZoneInfo("America/Sao_Paulo")


def event(key="nba", **kwargs):
    defaults = dict(id="test:1", competition=key, home="Time A", away="Time B", start=datetime(2026, 11, 26, 0, 30, tzinfo=TZ), season="regular-season")
    defaults.update(kwargs)
    return Event(**defaults)


class ScopeTests(unittest.TestCase):
    def test_midnight_date_and_exclusive_boundary(self):
        start, end = window(date(2026, 11, 25), CONFIG)
        game = event()
        self.assertTrue(start <= game.start < end)
        self.assertFalse(start <= end < end)
        text = render(Digest([game], [], start, end), CONFIG)
        self.assertIn("00h30 — 26/11/2026", text)

    def test_big_six_both_and_laliga_one(self):
        for away, expected in [("Chelsea", True), ("Everton", False), ("Tottenham", True)]:
            self.assertEqual(selection(event("premier_league", home="Arsenal", away=away), RULES["premier_league"])[0], expected)
        self.assertTrue(selection(event("la_liga", home="FC Barcelona"), RULES["la_liga"])[0])
        self.assertFalse(selection(event("la_liga"), RULES["la_liga"])[0])

    def test_paulista_four_clubs(self):
        self.assertTrue(selection(event("paulista_a1", away="São Paulo"), RULES["paulista_a1"])[0])
        self.assertFalse(selection(event("paulista_a1", away="Ponte Preta"), RULES["paulista_a1"])[0])

    def test_brazil_cup_stage(self):
        for phase, expected in [("4ª fase", False), ("5ª fase", True), ("Oitavas de final", True), ("Quartas de final", True), ("Final", True), ("", False)]:
            with self.subTest(phase=phase):
                self.assertEqual(selection(event("copa_do_brasil", phase=phase, season=""), RULES["copa_do_brasil"])[0], expected)

    def test_champions_qualifying_excluded_knockout_playoff_included(self):
        for season, expected in [("qualifying", False), ("qualifying-playoffs", False), ("league-phase", True), ("knockout-round-playoffs", True), ("final", True), ("", False)]:
            self.assertEqual(selection(event("champions_league", season=season), RULES["champions_league"])[0], expected)

    def test_preseason_and_regular_season(self):
        for key in ["nba", "nfl"]:
            self.assertFalse(selection(event(key, season="pre-season"), RULES[key])[0])
            self.assertTrue(selection(event(key, season="post-season"), RULES[key])[0])
        self.assertFalse(selection(event("nfl", season="post-season", phase="Pro Bowl"), RULES["nfl"])[0])

    def test_failed_consultation_is_not_no_games(self):
        start, end = window(date(2026, 11, 25), CONFIG)
        text = render(Digest([], ["NFL: fonte indisponível"], start, end), CONFIG)
        self.assertNotIn("Não haverá jogos", text)
        self.assertIn("Nenhum jogo confirmado", text)
        self.assertNotIn("confira os avisos abaixo", text)
        self.assertNotIn("NFL: fonte indisponível", text)
        text_with_games = render(Digest([event()], ["Globo SP oficial: fonte indisponível"], start, end), CONFIG)
        self.assertIn("Time A × Time B", text_with_games)
        self.assertNotIn("Consultas e dados incompletos", text_with_games)
        self.assertNotIn("Globo SP oficial: fonte indisponível", text_with_games)

    def test_long_messages_preserve_text_with_emojis(self):
        text = ("🏀 Time A × Time B\n" * 1000).strip()
        parts = split_messages(text)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p.encode("utf-16-le")) // 2 <= 3900 for p in parts))
        self.assertEqual("\n".join(parts), text)


class SourcesTests(unittest.TestCase):
    def test_real_source_aliases_merge_the_same_match(self):
        for first, second in [("LA Clippers", "Los Angeles Clippers"), ("Sabah FK", "Sabah"), ("Slavia Praga", "Slavia Prague"), ("VfB Stuttgart", "Stuttgart"), ("AS Roma", "Roma"), ("Sporting CP", "Sporting")]:
            self.assertEqual(team_key(first), team_key(second))

    def test_espn_discards_american_channels(self):
        data = {"leagues": [{"slug": "nba"}], "events": [{"id": "1", "date": "2026-11-26T03:30Z", "season": {"slug": "regular-season"}, "competitions": [{"competitors": [{"homeAway": "home", "team": {"displayName": "A"}}, {"homeAway": "away", "team": {"displayName": "B"}}], "broadcasts": [{"names": ["ESPN"]}], "geoBroadcasts": [{"region": "us", "media": {"shortName": "ESPN"}}, {"region": "br", "media": {"shortName": "Disney+"}}]}]}]}
        events, notes = espn.parse(data, "nba", "https://example.org")
        self.assertEqual(events[0].channels, ["Disney+"])
        self.assertEqual(events[0].start.astimezone(TZ).hour, 0)

    def test_ge_filters_advertising_and_marks_regional_uncertainty(self):
        match = {"id": 1, "firstContestant": {"popularName": "A"}, "secondContestant": {"popularName": "B"}, "startDate": "2026-11-25", "startHour": "21:00:00", "liveWatchSources": [{"name": "Cartola"}, {"name": "Globo"}, {"name": "Premiere"}], "phase": {"name": "Fase única"}}
        days = {"2026-11-25": {"championshipsAgenda": [{"championship": {"name": "Campeonato Brasileiro"}, "future": [{"match": match}]}]}}
        html = 'window.dataSportsSchedule = {sport: ' + json.dumps(days) + ', multisport: {}};'
        events, dates, warnings = ge.parse(html)
        self.assertEqual(len(events), 1)
        self.assertNotIn("Cartola", events[0].channels)
        self.assertIn("Globo (praça de São Paulo a confirmar)", events[0].channels)

    @patch("sports_digest.collector.ge.fetch")
    @patch("sports_digest.collector.espn.fetch")
    @patch("sports_digest.collector.broadcasts.fetch_overdrive", return_value=([], []))
    @patch("sports_digest.collector.broadcasts.fetch_hoops", return_value=([], []))
    @patch("sports_digest.collector.broadcasts.fetch_tvinside", return_value=([], []))
    @patch("sports_digest.collector.broadcasts.fetch_fawiki", return_value=([], []))
    @patch("sports_digest.collector.broadcasts.fetch_guide", return_value=([], []))
    @patch("sports_digest.collector.broadcasts.fetch_globo_sp", return_value=([], []))
    def test_partial_failure_keeps_confirmed_games_and_merges_channels(self, globo, guide, fawiki, tvinside, hoops, overdrive, espn_fetch, ge_fetch):
        def fetch(key, day):
            if key == "nfl":
                raise RuntimeError("offline")
            return ([event()] if key == "nba" else []), []
        espn_fetch.side_effect = fetch
        ge_fetch.return_value = ([event(id="ge:2", channels=["Disney+"])], {"2026-11-25", "2026-11-26"}, [])
        digest = collect(date(2026, 11, 25), CONFIG)
        self.assertEqual(len(digest.events), 1)
        self.assertEqual(digest.events[0].channels, ["Disney+"])
        self.assertTrue(any("NFL" in n for n in digest.warnings))


class DeliveryTests(unittest.TestCase):
    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "123"})
    @patch("sports_digest.telegram.time.sleep")
    @patch("sports_digest.telegram.send_one", return_value=101)
    def test_repeat_run_does_not_resend(self, send_one, sleep):
        with tempfile.TemporaryDirectory() as folder:
            day, state = date(2026, 11, 25), Path(folder)
            self.assertEqual(deliver(["primeira", "segunda"], day, state), 2)
            self.assertEqual(deliver(["resumo mudou"], day, state), 0)
            self.assertEqual(send_one.call_count, 2)

    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "123"})
    @patch("sports_digest.telegram.send_one", side_effect=DeliveryError("timeout"))
    def test_uncertain_delivery_never_automatically_resends(self, send_one):
        with tempfile.TemporaryDirectory() as folder:
            for _ in range(2):
                with self.assertRaises(DeliveryError):
                    deliver(["texto"], date(2026, 11, 25), Path(folder))
            self.assertEqual(send_one.call_count, 1)


if __name__ == "__main__":
    unittest.main()

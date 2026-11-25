from datetime import date, datetime, timedelta
import unittest
from zoneinfo import ZoneInfo
from sports_digest.models import Event
from sports_digest.sources.broadcasts import Listing, channels, enrich, hoops_url, parse_hoops, parse_overdrive, parse_tvinside
from sports_digest.http import SourceError

TZ = ZoneInfo("America/Sao_Paulo")


class BroadcastTests(unittest.TestCase):
    def test_tvguide_keeps_channel_number_and_ignores_replays(self):
        html = '''<div class="registro" dti="2026-11-25 22:00"><span class=titulo>NFL: Los Angeles Rams x Green Bay Packers</span></div><div class="registro" dti="2026-11-25 09:00"><span class=titulo>VT - NFL: Los Angeles Rams x Green Bay Packers</span></div>'''
        found = parse_tvinside(html, "ESPN 3", date(2026, 11, 25), "https://example.org")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].channels, ["ESPN 3"])

    def test_prime_accent_does_not_duplicate_platform(self):
        game = Event("1", "nba", "A", "B", datetime(2026, 11, 27, 21, tzinfo=TZ), channels=["Prime Video", "Prime Vídeo"])
        enrich([game], [])
        self.assertEqual(game.channels, ["Prime Video"])

    def test_numbered_espn_channels_stay_distinct(self):
        self.assertEqual(channels("ESPN 2 / ESPN3 · ESPN 4 · Disney+ Premium"), ["Disney+ Premium", "ESPN 2", "ESPN 3", "ESPN 4"])
        self.assertEqual(channels("Prime Video"), ["Prime Video"])
        self.assertNotIn("Prime Video", channels("NBA League Pass"))

    def test_overdrive_utc_time_and_numbered_channel(self):
        html = '''<div class="od-games__comp"><h3 class="od-games__league">NBA 2026/27</h3><ol><li class="od-game"><time class="od-game__time" datetime="2026-11-26T03:00:00+00:00">00:00</time><a class="od-game__name" href="https://example.org/match">San Antonio Spurs x Portland Trail Blazers</a><p class="od-game__tv"><span>Onde assistir: </span>ESPN 2 · Disney+ Premium</p></li></ol></div>'''
        found, notes = parse_overdrive(html)
        self.assertEqual(found[0].start.astimezone(TZ).date(), date(2026, 11, 26))
        self.assertIn("ESPN 2", found[0].channels)
        self.assertFalse(notes)

    def test_hoops_moves_midnight_to_next_civil_day(self):
        html = '''<div class="hb-post__texto"><p><strong>25/11/26 (quarta)</strong></p><p>Miami Heat x Philadelphia 76ers – 19h (ESPN 2/Disney+)<br>San Antonio Spurs x Portland Trail Blazers – 0h (ESPN 2/Disney+)</p></div>'''
        found, _ = parse_hoops(html, "https://example.org/calendar")
        self.assertEqual(found[0].start.date(), date(2026, 11, 25))
        self.assertEqual(found[1].start.date(), date(2026, 11, 26))

    def test_prime_and_season_rollover(self):
        html = '<div class="hb-post__texto"><p>27/11/26 (sexta)</p><p>Los Angeles Lakers x San Antonio Spurs – 23h30 (Prime Video)</p></div>'
        found, _ = parse_hoops(html, "https://example.org/prime")
        self.assertEqual(found[0].channels, ["Prime Video"])
        self.assertIn("nba-2026-27", hoops_url(date(2027, 1, 2), True))
        self.assertIn("nba-2027-28", hoops_url(date(2027, 10, 2), True))

    def test_replay_or_wrong_teams_do_not_enrich(self):
        game = Event("1", "nba", "Time A", "Time B", datetime(2026, 11, 25, 21, tzinfo=TZ))
        replay = Listing("nba", ("time a", "time b"), game.start - timedelta(hours=12), ["ESPN 2"], "https://example.org", "Teste")
        wrong = Listing("nba", ("time a", "time c"), game.start, ["ESPN 3"], "https://example.org", "Teste")
        warnings = enrich([game], [replay, wrong])
        self.assertFalse(game.channels)
        self.assertTrue(warnings)

    def test_enrichment_evidence_and_generic_channel_refinement(self):
        game = Event("1", "nba", "Time A", "Time B", datetime(2026, 11, 25, 21, tzinfo=TZ), channels=["ESPN", "Disney+"])
        listing = Listing("nba", ("time a", "time b"), game.start, ["ESPN 2", "Disney+ Premium"], "https://example.org", "Teste")
        enrich([game], [listing])
        self.assertEqual(game.channels, ["Disney+ Premium", "ESPN 2"])
        self.assertEqual(game.broadcast_evidence[0]["country"], "BR")
        self.assertTrue(game.broadcast_evidence[0]["checked_at"])

    def test_invalid_html_is_failure_not_empty_confirmation(self):
        for parser in [parse_overdrive, lambda html: parse_hoops(html, "https://example.org")]:
            with self.assertRaises(SourceError):
                parser("<html>verificação de acesso</html>")


if __name__ == "__main__":
    unittest.main()

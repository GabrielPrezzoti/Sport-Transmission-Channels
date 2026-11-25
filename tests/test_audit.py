from datetime import datetime, timedelta
import json
from html import escape
import unittest
from zoneinfo import ZoneInfo
from sports_digest.models import Event
from sports_digest.sources.broadcasts import Listing, enrich, parse_fawiki, parse_globo_sp, parse_guide, channels, competition_key
from sports_digest.http import SourceError

TZ = ZoneInfo("America/Sao_Paulo")


class AuditTests(unittest.TestCase):
    def test_numbered_channels_conflict_is_not_silent_union(self):
        game = Event("1", "nfl", "A", "B", datetime(2026, 11, 25, 22, tzinfo=TZ))
        listings = [Listing("nfl", ("a", "b"), game.start, [channel], "https://example.org/" + source, source) for source, channel in [("Fonte A", "ESPN 2"), ("Fonte B", "ESPN 3")]]
        warnings = enrich([game], listings)
        self.assertTrue(warnings)
        self.assertNotIn("ESPN 2", game.channels)
        self.assertNotIn("ESPN 3", game.channels)
        self.assertIn("ESPN (número a confirmar)", game.channels)
        self.assertEqual(len(game.broadcast_evidence), 2)

    def test_omitted_channel_is_not_a_conflict(self):
        game = Event("1", "nba", "A", "B", datetime(2026, 11, 25, 22, tzinfo=TZ))
        listings = [Listing("nba", ("a", "b"), game.start, [c], "https://example.org", s) for s, c in [("A", "ESPN 2"), ("B", "NBA League Pass (assinatura adicional)")]]
        self.assertFalse(enrich([game], listings))
        self.assertIn("ESPN 2", game.channels)

    def test_prime_addon_is_not_prime_included(self):
        self.assertEqual(channels("NBA League Pass via Prime Video"), [])
        self.assertNotIn("Prime Video", channels("NFL Game Pass no DAZN"))

    def test_guide_requires_named_match_and_rejects_replay(self):
        events = [{"name": n, "startDate": "2026-11-25T22:00:00-03:00"} for n in ["NFL: A x B - Ao Vivo", "VT - NFL: A x B", "NFL - Ao Vivo", "NCAA: A x B"]]
        html = '<script type="application/ld+json">' + json.dumps({"@type": "TelevisionChannel", "broadcastEvent": events}) + '</script>'
        found, notes = parse_guide(html, "ESPN 3", "https://example.org")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].teams, ("a", "b"))

    def test_fawiki_final_cards_with_time_without_css_class(self):
        html = '<article class="schedule-card"><a class="schedule-team"><strong>A</strong></a><a class="schedule-team"><strong>B</strong></a><time datetime="2026-11-22T15:00:00-03:00">15h00</time><strong class="schedule-broadcast-links">ESPN 3 · Disney+ · NFL Game Pass no DAZN</strong></article>'
        found, notes = parse_fawiki(html, "https://example.org")
        self.assertEqual(found[0].channels, ["Disney+", "ESPN 3", "NFL Game Pass (DAZN; assinatura adicional)"])
        self.assertFalse(notes)

    def test_official_regional_pregame_interval(self):
        data = {"channelCode": "GGP1", "modified": "2026-11-25T19:00:00Z", "output": [{"slots": [{"name": "Final da Libertadores - Palmeiras x Estudiantes", "scheduledDate": "2026-11-28T16:15:00-03:00", "duration": "03:20:00"}]}]}
        html = '<main data-props="' + escape(json.dumps({"context": {"gridData": {"data": data}}}), quote=True) + '"></main>'
        listings, notes = parse_globo_sp(html)
        game = Event("1", "libertadores", "Palmeiras", "Estudiantes de La Plata", datetime(2026, 11, 28, 17, tzinfo=TZ), channels=["Globo (praça de São Paulo a confirmar)"])
        self.assertFalse(enrich([game], listings))
        self.assertEqual(game.channels, ["Globo (São Paulo capital)"])
        self.assertTrue(game.broadcast_evidence[0]["updated_at"])
        data["channelCode"] = "OTHER"
        with self.assertRaises(SourceError):
            parse_globo_sp('<main data-props="' + escape(json.dumps({"context": {"gridData": {"data": data}}}), quote=True) + '"></main>')

    def test_football_competition_mapping_excludes_other_divisions_and_gender(self):
        for name in ["Campeonato Brasileiro Série B", "Brasileirão feminino", "Copa do Brasil sub-20"]:
            self.assertIsNone(competition_key(name))
        self.assertEqual(competition_key("Champions League — 5ª rodada"), "champions_league")


if __name__ == "__main__":
    unittest.main()

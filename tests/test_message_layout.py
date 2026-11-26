from datetime import date, datetime
from pathlib import Path
import json
import unittest
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from sports_digest.collector import Digest, window
from sports_digest.formatter import render, split_messages, display_channels
from sports_digest.models import Event
from sports_digest.telegram import send_one
from test_digest import CONFIG


class LayoutTests(unittest.TestCase):
    def test_bold_teams_escaped_channels_and_blank_line_between_games(self):
        start, end = window(date(2026, 11, 26), CONFIG)
        games = [Event(str(i), "nba", 'A & B', 'C < D', start, channels=['ESPN 2', 'Prime Video']) for i in range(2)]
        text = render(Digest(games, [], start, end), CONFIG)
        ET.fromstring('<root>' + text + '</root>')
        self.assertIn('<b>A &amp; B × C &lt; D</b>', text)
        self.assertIn('📺 ESPN 2 · Prime Video\n\n<b>A', text)
        self.assertEqual(text.count('🏀 NBA'), 1)
        self.assertNotIn('Fontes consultadas:', text)
        self.assertEqual(display_channels(['sportv', 'SporTV', 'Ge TV', 'ge tv', 'globoplay']), ['SporTV', 'Globoplay', 'ge tv'])

    def test_game_blocks_remain_together_when_splitting(self):
        block = '<b>Time A × Time B</b>\n19h00\n📺 ESPN 2'
        parts = split_messages('\n\n'.join([block] * 8), limit=100)
        for part in parts:
            ET.fromstring('<root>' + part + '</root>')
            self.assertEqual(part.count('<b>'), part.count('📺'))

    def test_oversized_bold_block_keeps_entities_tags_and_text(self):
        text = '<b>' + ('A &amp; B 🏀 ' * 500) + '</b>'
        parts = split_messages(text, limit=100)
        visible = []
        for part in parts:
            root = ET.fromstring('<root>' + part + '</root>')
            visible.append(''.join(root.itertext()))
            self.assertLessEqual(len(part.encode('utf-16-le')) // 2, 100)
        original = ET.fromstring('<root>' + text + '</root>')
        self.assertEqual(''.join(visible), ''.join(original.itertext()))

    @patch('sports_digest.telegram.urllib.request.urlopen')
    def test_telegram_payload_enables_html(self, urlopen):
        response = MagicMock()
        response.read.return_value = b'{"ok": true, "result": {"message_id": 1}}'
        urlopen.return_value.__enter__.return_value = response
        self.assertEqual(send_one('fake', '123', '<b>A × B</b>'), 1)
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload['parse_mode'], 'HTML')

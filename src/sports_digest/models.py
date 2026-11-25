from dataclasses import dataclass, field
from datetime import datetime
import re
import unicodedata


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


ALIASES = {
    "tottenham": "tottenham hotspur", "fc barcelona": "barcelona",
    "sao paulo fc": "sao paulo", "corinthians paulista": "corinthians",
    "internazionale": "inter milan", "internazionale milano": "inter milan",
    "inter de milao": "inter milan", "atletico mineiro": "atletico mg",
    "atletico paranaense": "athletico pr", "athletico paranaense": "athletico pr",
    "vitoria ba": "vitoria", "bayern de munique": "bayern munich",
    "bayern munchen": "bayern munich", "atletico de madrid": "atletico madrid",
    "borussia dortmund": "borussia dortmund", "new york knicks": "new york knicks",
    "sabah fk": "sabah", "slavia praga": "slavia prague", "villareal": "villarreal",
    "viking fk": "viking", "vfb stuttgart": "stuttgart", "as roma": "roma",
    "sporting cp": "sporting", "la clippers": "los angeles clippers",
    "la lakers": "los angeles lakers",
    "psg": "paris saint germain", "estudiantes de la plata": "estudiantes",
}


def team_key(name: str) -> str:
    name = normalize(name)
    return ALIASES.get(name, name)


@dataclass
class Event:
    id: str
    competition: str
    home: str
    away: str
    start: datetime
    phase: str = ""
    season: str = ""
    status: str = ""
    time_confirmed: bool = True
    channels: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    broadcast_evidence: list[dict] = field(default_factory=list)

    @property
    def match_key(self):
        return self.competition, tuple(sorted((team_key(self.home), team_key(self.away))))

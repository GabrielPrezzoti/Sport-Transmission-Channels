import json
import time
import urllib.error
import urllib.request


class SourceError(RuntimeError):
    pass


def get_text(url: str) -> str:
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "SportsDigest/0.1 (personal sports schedule)", "Accept": "application/json,text/html"})
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise SourceError(f"HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError, UnicodeError):
            pass
        if attempt < 2:
            time.sleep(attempt + 1)
    raise SourceError("Fonte indisponível após 3 tentativas")


def get_json(url: str):
    try:
        return json.loads(get_text(url))
    except ValueError:
        raise SourceError("Resposta JSON inválida") from None

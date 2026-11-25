"""Envio com registro por parte e interrupção em caso de entrega ambígua."""
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
import time


class DeliveryError(RuntimeError):
    pass


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def send_one(token, chat_id, text):
    # Nunca incluir token, URL, chat_id ou resposta bruta em exceções/logs.
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text, "link_preview_options": {"is_disabled": True}}).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        if not result.get("ok"):
            raise DeliveryError("Telegram recusou a mensagem; conferir configuração")
        return result["result"]["message_id"]
    except urllib.error.HTTPError as exc:
        raise DeliveryError(f"Telegram retornou HTTP {exc.code}; entrega pendente de revisão") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError):
        raise DeliveryError("Resposta de envio incerta. Confira a conversa antes de tentar novamente") from None


def deliver(messages, day, state_dir=Path(".state")):
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise DeliveryError("Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID nos segredos do ambiente")
    recipient = hashlib.sha256(chat_id.encode()).hexdigest()[:16]
    path = state_dir / f"{day.isoformat()}-{recipient}.json"
    if path.exists():
        ledger = json.loads(path.read_text(encoding="utf-8"))
    else:
        ledger = {"date": day.isoformat(), "parts": [{"text": text, "status": "new"} for text in messages]}
        save(path, ledger)
    sent = 0
    # Reutilizar o resumo original em retomadas; a coleta pode ter mudado.
    for part in ledger["parts"]:
        if part["status"] == "sent":
            continue
        if part["status"] == "pending":
            raise DeliveryError("Existe um envio de resultado incerto no registro. Confira o Telegram e reconcilie o estado antes de reenviar")
        part["status"] = "pending"
        save(path, ledger)
        message_id = send_one(token, chat_id, part["text"])
        part.update(status="sent", message_id=message_id)
        save(path, ledger)
        sent += 1
        time.sleep(1.1)
    return sent

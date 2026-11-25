"""Consulta local para descobrir o chat privado, sem expor o token."""
import json
import os
import urllib.request
from getpass import getpass


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN") or getpass("Token do BotFather (entrada oculta): ")
    if not token:
        raise SystemExit("Defina TELEGRAM_BOT_TOKEN no ambiente antes de executar.")
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20) as response:
            data = json.load(response)
        chats = {}
        for update in data.get("result", []):
            chat = update.get("message", {}).get("chat", {})
            if chat.get("type") == "private":
                chats[chat["id"]] = chat.get("first_name", "Conversa privada")
        if not chats:
            print("Nenhuma conversa encontrada. Abra seu bot no Telegram, envie /start e repita.")
        for chat_id, name in chats.items():
            print(f"{name}: TELEGRAM_CHAT_ID={chat_id}")
    except Exception:
        raise SystemExit("Não foi possível consultar o Telegram. Confira token e conexão; o token não será exibido.") from None


if __name__ == "__main__":
    main()

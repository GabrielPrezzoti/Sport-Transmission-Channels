import argparse
from dataclasses import asdict
from datetime import date, datetime
import json
from pathlib import Path
import tomllib
from zoneinfo import ZoneInfo
from .collector import collect
from .formatter import render, split_messages
from .telegram import DeliveryError, deliver


def main():
    parser = argparse.ArgumentParser(description="Agenda esportiva diária; padrão: prévia, sem envio")
    parser.add_argument("--config", type=Path, default=Path("config/preferences.toml"))
    parser.add_argument("--date", type=date.fromisoformat, help="Data do resumo (AAAA-MM-DD), no fuso de Brasília")
    parser.add_argument("--send", action="store_true", help="Enviar ao Telegram usando os segredos do ambiente")
    parser.add_argument("--force-resend", action="store_true", help="Reenviar o resumo atual mesmo se já enviado nesta data (requer --send)")
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--state-dir", type=Path, default=Path(".state"))
    args = parser.parse_args()
    if args.force_resend and not args.send:
        parser.error("--force-resend requer --send")
    with args.config.open("rb") as file:
        config = tomllib.load(file)
    day = args.date or datetime.now(ZoneInfo(config["timezone"])).date()
    digest = collect(day, config)
    text = render(digest, config)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / f"{day}.txt").write_text(text, encoding="utf-8")
    (args.output / f"{day}.json").write_text(json.dumps(asdict(digest), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(text)
    if args.send:
        if not config["delivery"]["enabled"]:
            parser.exit(2, "Envio desativado: configure delivery.enabled = true após validar a prévia.\n")
        try:
            sent = deliver(split_messages(text), day, args.state_dir, force_resend=args.force_resend)
        except DeliveryError as exc:
            parser.exit(1, f"Falha no envio: {exc}\n")
        print(f"Partes enviadas nesta execução: {sent}")
        if sent == 0:
            print("Envio ignorado: o registro desta data e destinatário já está concluído.")


if __name__ == "__main__":
    main()

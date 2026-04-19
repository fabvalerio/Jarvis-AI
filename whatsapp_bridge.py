#!/usr/bin/env python3
"""
WhatsApp Bridge para Jarvis - Integração via Evolution API (Open Source)
Permite enviar/receber mensagens WhatsApp, imagens e comandos remotos.

Requisitos:
  - Evolution API rodando (docker ou local): https://github.com/EvolutionAPI/evolution-api
  - WHATSAPP_API_URL e WHATSAPP_API_KEY no .env

Alternativa cloud (sem self-host): defina WHATSAPP_USE_CLOUD=true no .env
"""

import os
import json
import asyncio
import logging
import threading
import base64
from datetime import datetime
from typing import Optional, Callable
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class EvolutionAPIClient:
    """Cliente REST para a Evolution API (open source WhatsApp API)."""

    def __init__(self, base_url: str, api_key: str, instance: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.instance = instance
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": self.api_key,
            "Content-Type": "application/json",
        })

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path}"

    def create_instance(self) -> dict:
        """Cria/conecta instância WhatsApp."""
        payload = {
            "instanceName": self.instance,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
        }
        r = self.session.post(self._url("instance/create"), json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def get_qrcode(self) -> Optional[str]:
        """Retorna QR code em base64 para autenticação."""
        r = self.session.get(
            self._url(f"instance/connect/{self.instance}"), timeout=30
        )
        r.raise_for_status()
        data = r.json()
        return data.get("base64") or data.get("qrcode", {}).get("base64")

    def get_connection_state(self) -> str:
        """Retorna estado da conexão: open | close | connecting."""
        r = self.session.get(
            self._url(f"instance/connectionState/{self.instance}"), timeout=15
        )
        r.raise_for_status()
        return r.json().get("instance", {}).get("state", "close")

    def send_text(self, to: str, text: str) -> dict:
        """Envia mensagem de texto."""
        payload = {
            "number": self._normalize_number(to),
            "text": text,
        }
        r = self.session.post(
            self._url(f"message/sendText/{self.instance}"), json=payload, timeout=30
        )
        r.raise_for_status()
        return r.json()

    def send_image(self, to: str, image_path: str, caption: str = "") -> dict:
        """Envia imagem a partir de um arquivo local."""
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = Path(image_path).suffix.lstrip(".") or "png"
        payload = {
            "number": self._normalize_number(to),
            "mediatype": "image",
            "mimetype": f"image/{ext}",
            "caption": caption,
            "media": b64,
            "fileName": Path(image_path).name,
        }
        r = self.session.post(
            self._url(f"message/sendMedia/{self.instance}"), json=payload, timeout=60
        )
        r.raise_for_status()
        return r.json()

    def send_image_url(self, to: str, url: str, caption: str = "") -> dict:
        """Envia imagem a partir de uma URL."""
        payload = {
            "number": self._normalize_number(to),
            "mediatype": "image",
            "caption": caption,
            "media": url,
        }
        r = self.session.post(
            self._url(f"message/sendMedia/{self.instance}"), json=payload, timeout=60
        )
        r.raise_for_status()
        return r.json()

    def set_webhook(self, webhook_url: str) -> dict:
        """Configura webhook para receber mensagens."""
        payload = {
            "url": webhook_url,
            "webhook_by_events": True,
            "webhook_base64": False,
            "events": ["MESSAGES_UPSERT"],
        }
        r = self.session.post(
            self._url(f"webhook/set/{self.instance}"), json=payload, timeout=30
        )
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _normalize_number(number: str) -> str:
        """Normaliza número: remove +, espaços. Ex: +55 11 99999-9999 -> 5511999999999"""
        return "".join(filter(str.isdigit, number))


class WhatsAppBridge:
    """
    Bridge completo: recebe comandos via WhatsApp e integra com Jarvis.

    Como usar:
        bridge = WhatsAppBridge(jarvis_instance=meu_jarvis)
        bridge.start()   # roda em background thread
        bridge.send_message("5511999999999", "Olá do Jarvis!")
    """

    def __init__(self, jarvis_instance=None):
        self.jarvis_instance = jarvis_instance
        self.authorized_number: Optional[str] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None

        # Configurações via env
        self.api_url = os.getenv("WHATSAPP_API_URL", "http://localhost:8080")
        self.api_key = os.getenv("WHATSAPP_API_KEY", "")
        self.instance = os.getenv("WHATSAPP_INSTANCE", "jarvis")

        self.client = EvolutionAPIClient(self.api_url, self.api_key, self.instance)
        self._load_auth()

        # Mapa de comandos disponíveis
        self.commands = {
            "/ajuda": self._cmd_help,
            "/status": self._cmd_status,
            "/hora": self._cmd_time,
            "/imagem": self._cmd_generate_image,
            "/cronograma": self._cmd_schedule,
        }

    # ------------------------------------------------------------------ #
    # Persistência de autorização
    # ------------------------------------------------------------------ #

    def _load_auth(self):
        auth_file = Path("whatsapp_auth.json")
        if auth_file.exists():
            try:
                data = json.loads(auth_file.read_text())
                self.authorized_number = data.get("number")
            except Exception:
                pass

    def _save_auth(self, number: str):
        Path("whatsapp_auth.json").write_text(json.dumps({"number": number}))
        self.authorized_number = number

    def is_authorized(self, number: str) -> bool:
        clean = EvolutionAPIClient._normalize_number(number)
        if not self.authorized_number:
            self._save_auth(clean)
            return True
        return clean == self.authorized_number

    # ------------------------------------------------------------------ #
    # Envio de mensagens (API pública para outros módulos usarem)
    # ------------------------------------------------------------------ #

    def send_message(self, to: str, text: str):
        """Envia mensagem de texto para um número."""
        try:
            self.client.send_text(to, text)
        except Exception as e:
            logger.error(f"WhatsApp send_message erro: {e}")

    def send_image(self, to: str, image_path: str, caption: str = ""):
        """Envia imagem de um arquivo local."""
        try:
            self.client.send_image(to, image_path, caption)
        except Exception as e:
            logger.error(f"WhatsApp send_image erro: {e}")

    def broadcast(self, text: str):
        """Envia mensagem para o número autorizado."""
        if self.authorized_number:
            self.send_message(self.authorized_number, text)

    # ------------------------------------------------------------------ #
    # Processamento de mensagens recebidas (webhook payload)
    # ------------------------------------------------------------------ #

    def handle_incoming(self, payload: dict):
        """
        Processa payload JSON do webhook da Evolution API.
        Chame este método no seu endpoint HTTP de webhook.
        """
        try:
            data = payload.get("data", {})
            key = data.get("key", {})
            from_me = key.get("fromMe", False)
            if from_me:
                return  # ignora mensagens próprias

            sender = key.get("remoteJid", "").split("@")[0]
            msg_obj = data.get("message", {})
            text = (
                msg_obj.get("conversation")
                or msg_obj.get("extendedTextMessage", {}).get("text", "")
            ).strip()

            if not text:
                return

            logger.info(f"WhatsApp recebido de {sender}: {text}")

            if not self.is_authorized(sender):
                self.send_message(sender, "Acesso nao autorizado.")
                return

            self._dispatch(sender, text)

        except Exception as e:
            logger.error(f"handle_incoming erro: {e}")

    def _dispatch(self, sender: str, text: str):
        """Roteia mensagem para comando ou Jarvis."""
        for cmd, handler in self.commands.items():
            if text.lower().startswith(cmd):
                arg = text[len(cmd):].strip()
                handler(sender, arg)
                return

        # Sem comando explícito: envia para Jarvis
        self._process_with_jarvis(sender, text)

    # ------------------------------------------------------------------ #
    # Comandos disponíveis via WhatsApp
    # ------------------------------------------------------------------ #

    def _cmd_help(self, sender: str, _arg: str):
        msg = (
            "Comandos disponíveis:\n"
            "/ajuda - Esta mensagem\n"
            "/status - Status do sistema\n"
            "/hora - Hora atual\n"
            "/imagem <descrição> - Gera imagem AI\n"
            "/cronograma <pedido> - Cria cronograma\n"
            "\nOu envie qualquer texto para o Jarvis responder!"
        )
        self.send_message(sender, msg)

    def _cmd_status(self, sender: str, _arg: str):
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        msg = (
            f"Status Jarvis\n"
            f"CPU: {cpu}%\n"
            f"RAM: {ram}%\n"
            f"Horario: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
            f"Conexao WhatsApp: Ativa"
        )
        self.send_message(sender, msg)

    def _cmd_time(self, sender: str, _arg: str):
        self.send_message(sender, f"Sao {datetime.now().strftime('%H:%M')} de {datetime.now().strftime('%d/%m/%Y')}.")

    def _cmd_generate_image(self, sender: str, arg: str):
        """Gera imagem via jarvis_image_generator e envia."""
        if not arg:
            self.send_message(sender, "Informe a descricao: /imagem um post sobre tecnologia")
            return
        self.send_message(sender, f"Gerando imagem: '{arg}'...")
        try:
            from jarvis_image_generator import JarvisImageGenerator
            gen = JarvisImageGenerator()
            result = gen.generate_social_post(arg)
            if result.get("success"):
                self.send_image(sender, result["path"], caption=result.get("caption", arg))
            else:
                self.send_message(sender, f"Erro ao gerar imagem: {result.get('error', 'desconhecido')}")
        except Exception as e:
            self.send_message(sender, f"Erro: {e}")

    def _cmd_schedule(self, sender: str, arg: str):
        """Cria cronograma via jarvis_scheduler e envia."""
        if not arg:
            self.send_message(sender, "Informe o pedido: /cronograma semana de lancamento de produto")
            return
        self.send_message(sender, f"Criando cronograma para: '{arg}'...")
        try:
            from jarvis_scheduler import JarvisScheduler
            sched = JarvisScheduler()
            result = sched.create_schedule(arg)
            self.send_message(sender, result)
        except Exception as e:
            self.send_message(sender, f"Erro: {e}")

    def _process_with_jarvis(self, sender: str, text: str):
        """Envia texto para o core do Jarvis e retorna resposta."""
        try:
            if self.jarvis_instance and hasattr(self.jarvis_instance, "process_command"):
                response = self.jarvis_instance.process_command(text)
            else:
                response = self._fallback_gemini(text)
            self.send_message(sender, response)
        except Exception as e:
            self.send_message(sender, f"Erro ao processar: {e}")

    def _fallback_gemini(self, text: str) -> str:
        """Usa Gemini diretamente se Jarvis não estiver conectado."""
        try:
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key:
                return "Jarvis nao esta conectado. Inicie o sistema principal."
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            r = model.generate_content(
                f"Responda de forma concisa (max 200 palavras) em portugues: {text}"
            )
            return r.text
        except Exception as e:
            return f"Erro Gemini: {e}"

    # ------------------------------------------------------------------ #
    # Inicialização e loop de polling (alternativa ao webhook)
    # ------------------------------------------------------------------ #

    def connect(self) -> bool:
        """Tenta conectar à instância WhatsApp. Retorna True se já está aberta."""
        try:
            state = self.client.get_connection_state()
            if state == "open":
                logger.info("WhatsApp já conectado.")
                return True
            logger.info("Criando instância WhatsApp...")
            self.client.create_instance()
            return False
        except Exception as e:
            logger.error(f"WhatsApp connect erro: {e}")
            return False

    def get_qrcode_ascii(self) -> Optional[str]:
        """Retorna QR code base64 (mostre no terminal ou GUI para autenticar)."""
        try:
            return self.client.get_qrcode()
        except Exception as e:
            logger.error(f"QR code erro: {e}")
            return None

    def start(self, background: bool = True):
        """Inicia o bridge. Se background=True, roda em thread separada."""
        if background:
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
        else:
            self._run_loop()

    def stop(self):
        self.running = False

    def _run_loop(self):
        """Loop principal: monitora conexão e exibe instruções."""
        self.running = True
        print("WhatsApp Bridge iniciado.")
        print(f"  API URL : {self.api_url}")
        print(f"  Instância: {self.instance}")
        connected = self.connect()
        if not connected:
            qr = self.get_qrcode_ascii()
            if qr:
                print("Escaneie o QR Code no WhatsApp para autenticar.")
                print(f"QR (base64): {qr[:80]}...")
            else:
                print("Aguardando conexao WhatsApp. Configure o webhook para receber mensagens.")
        else:
            print("WhatsApp conectado. Webhook ativo para receber mensagens.")
        print("Numero autorizado:", self.authorized_number or "Primeiro usuario a enviar mensagem")


class JarvisWhatsAppBridge:
    """Interface de alto nível para uso em outros módulos do Jarvis."""

    def __init__(self, jarvis_instance=None):
        self.bridge = WhatsAppBridge(jarvis_instance)

    def start(self):
        self.bridge.start(background=True)
        return self.bridge

    def send(self, to: str, text: str):
        self.bridge.send_message(to, text)

    def send_image(self, to: str, path: str, caption: str = ""):
        self.bridge.send_image(to, path, caption)

    def on_webhook(self, payload: dict):
        """Ponto de entrada para webhook HTTP — integre com Flask/FastAPI."""
        self.bridge.handle_incoming(payload)


def main():
    """Teste standalone do bridge."""
    logging.basicConfig(level=logging.INFO)
    bridge = JarvisWhatsAppBridge()
    b = bridge.start()
    print("Bridge rodando. Pressione Ctrl+C para sair.")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        b.stop()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Jarvis Image Generator - Geração de imagens AI para posts e conteúdos.

Suporta múltiplos backends (em ordem de prioridade):
  1. Stability AI (Stable Diffusion) - API gratuita com créditos
  2. Pollinations AI - 100% gratuito, sem API key
  3. Pillow template engine - fallback offline sem dependências externas

Uso:
    gen = JarvisImageGenerator()

    # Post para redes sociais
    result = gen.generate_social_post("Promoção de verão 50% off")

    # Imagem personalizada
    result = gen.generate_image("um robô futurista em cidade neon", style="cinematic")

    # Cronograma visual
    result = gen.generate_schedule_card(schedule_text, title="Semana de Lançamento")

    if result["success"]:
        print(result["path"])   # caminho do arquivo gerado
        print(result["caption"])  # legenda sugerida pela IA
"""

import os
import io
import json
import time
import base64
import hashlib
import logging
import textwrap
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Diretório de saída padrão
# ------------------------------------------------------------------ #
OUTPUT_DIR = Path(os.getenv("IMAGE_OUTPUT_DIR", "jarvis_images"))
OUTPUT_DIR.mkdir(exist_ok=True)


# ------------------------------------------------------------------ #
# Backend 1: Stability AI (gratuito com conta)
# ------------------------------------------------------------------ #

class StabilityAIBackend:
    API_URL = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate(self, prompt: str, width: int = 1024, height: int = 1024) -> Optional[bytes]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "text_prompts": [{"text": prompt, "weight": 1}],
            "cfg_scale": 7,
            "height": height,
            "width": width,
            "samples": 1,
            "steps": 30,
        }
        r = requests.post(self.API_URL, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        b64 = data["artifacts"][0]["base64"]
        return base64.b64decode(b64)


# ------------------------------------------------------------------ #
# Backend 2: Pollinations AI (100% gratuito, sem key)
# ------------------------------------------------------------------ #

class PollinationsBackend:
    BASE_URL = "https://image.pollinations.ai/prompt"

    def generate(self, prompt: str, width: int = 1024, height: int = 1024) -> Optional[bytes]:
        import urllib.parse
        encoded = urllib.parse.quote(prompt)
        url = f"{self.BASE_URL}/{encoded}?width={width}&height={height}&nologo=true&enhance=true"
        r = requests.get(url, timeout=90)
        r.raise_for_status()
        return r.content


# ------------------------------------------------------------------ #
# Backend 3: Template Pillow (offline, sem dependência externa)
# ------------------------------------------------------------------ #

class PillowTemplateBackend:
    """Cria posts visualmente atraentes usando apenas Pillow."""

    THEMES = {
        "tech": {"bg": (10, 10, 30), "accent": (0, 150, 255), "text": (255, 255, 255)},
        "nature": {"bg": (20, 50, 20), "accent": (80, 200, 80), "text": (240, 255, 240)},
        "business": {"bg": (20, 20, 20), "accent": (200, 160, 0), "text": (255, 255, 255)},
        "health": {"bg": (240, 248, 255), "accent": (0, 180, 100), "text": (20, 20, 60)},
        "default": {"bg": (15, 15, 40), "accent": (120, 80, 255), "text": (255, 255, 255)},
    }

    def generate(self, title: str, body: str = "", theme: str = "default",
                 width: int = 1080, height: int = 1080) -> bytes:
        from PIL import Image, ImageDraw, ImageFont

        colors = self.THEMES.get(theme, self.THEMES["default"])
        img = Image.new("RGB", (width, height), colors["bg"])
        draw = ImageDraw.Draw(img)

        # Gradiente simples (linhas horizontais)
        for y in range(height):
            alpha = y / height
            r = int(colors["bg"][0] * (1 - alpha * 0.4))
            g = int(colors["bg"][1] * (1 - alpha * 0.3))
            b = int(colors["bg"][2] + (30 * alpha))
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Borda decorativa
        border = 20
        draw.rectangle(
            [border, border, width - border, height - border],
            outline=colors["accent"], width=4
        )
        draw.rectangle(
            [border + 8, border + 8, width - border - 8, height - border - 8],
            outline=(*colors["accent"][:3], 80), width=1
        )

        # Linha decorativa superior
        accent_y = 120
        draw.rectangle([border + 20, accent_y, width - border - 20, accent_y + 4],
                       fill=colors["accent"])

        # Tenta carregar fonte, usa default se não disponível
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
            font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        except Exception:
            font_title = ImageFont.load_default()
            font_body = font_title
            font_small = font_title

        # Título
        title_lines = textwrap.wrap(title, width=22)
        y_pos = 160
        for line in title_lines[:4]:
            draw.text((width // 2, y_pos), line, font=font_title,
                      fill=colors["text"], anchor="mm")
            y_pos += 70

        # Corpo
        if body:
            y_pos += 30
            body_lines = textwrap.wrap(body, width=38)
            for line in body_lines[:8]:
                draw.text((width // 2, y_pos), line, font=font_body,
                          fill=(*colors["text"][:3],), anchor="mm")
                y_pos += 44

        # Rodapé com marca e data
        draw.text(
            (width // 2, height - 55),
            f"Jarvis AI  •  {datetime.now().strftime('%d/%m/%Y')}",
            font=font_small, fill=colors["accent"], anchor="mm"
        )

        # Elemento decorativo: círculo de fundo
        cx, cy = width - 100, 80
        r_size = 60
        draw.ellipse([cx - r_size, cy - r_size, cx + r_size, cy + r_size],
                     outline=colors["accent"], width=3)
        draw.text((cx, cy), "AI", font=font_small, fill=colors["accent"], anchor="mm")

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


# ------------------------------------------------------------------ #
# Gerador principal
# ------------------------------------------------------------------ #

class JarvisImageGenerator:
    """
    Gerador de imagens inteligente com múltiplos backends.
    Seleciona automaticamente o melhor backend disponível.
    """

    def __init__(self):
        self.stability_key = os.getenv("STABILITY_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")

        # Ordena backends: Stability > Pollinations > Pillow
        self._backends = []
        if self.stability_key:
            self._backends.append(("stability", StabilityAIBackend(self.stability_key)))
        self._backends.append(("pollinations", PollinationsBackend()))
        self._backends.append(("pillow", PillowTemplateBackend()))

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #

    def generate_social_post(
        self,
        topic: str,
        style: str = "modern",
        size: str = "square",
        save: bool = True,
    ) -> dict:
        """
        Gera um post para redes sociais.

        Args:
            topic: Tema/assunto do post (ex: "Promoção de verão 50% off")
            style: Estilo visual (modern | cinematic | minimal | vibrant)
            size: Formato (square=1080x1080 | story=1080x1920 | landscape=1280x720)
            save: Se True, salva em disco e retorna o caminho

        Returns:
            dict com keys: success, path, caption, backend, error
        """
        dims = {"square": (1080, 1080), "story": (1080, 1920), "landscape": (1280, 720)}
        w, h = dims.get(size, (1080, 1080))

        # Gera caption via Gemini
        caption = self._ai_caption(topic)

        # Monta prompt visual aprimorado
        visual_prompt = self._build_visual_prompt(topic, style)

        return self._generate_and_save(
            prompt=visual_prompt,
            filename_prefix=f"post_{size}",
            width=w,
            height=h,
            caption=caption,
            pillow_title=topic,
            pillow_body=caption[:120] if caption else "",
            pillow_theme=self._topic_to_theme(topic),
        )

    def generate_image(self, description: str, style: str = "cinematic",
                       width: int = 1024, height: int = 1024) -> dict:
        """Gera imagem de propósito geral a partir de descrição."""
        prompt = self._build_visual_prompt(description, style)
        return self._generate_and_save(
            prompt=prompt,
            filename_prefix="img",
            width=width, height=height,
            caption=description,
            pillow_title=description,
        )

    def generate_schedule_card(self, schedule_text: str, title: str = "Cronograma") -> dict:
        """Gera card visual com cronograma."""
        backend = PillowTemplateBackend()
        image_bytes = backend.generate(
            title=title,
            body=schedule_text[:400],
            theme="business",
            width=1080,
            height=1350,
        )
        path = self._save_bytes(image_bytes, "schedule")
        return {"success": True, "path": str(path), "caption": title, "backend": "pillow"}

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _generate_and_save(self, prompt: str, filename_prefix: str,
                           width: int, height: int, caption: str = "",
                           pillow_title: str = "", pillow_body: str = "",
                           pillow_theme: str = "default") -> dict:
        for name, backend in self._backends:
            try:
                logger.info(f"Tentando backend: {name}")
                if name == "pillow":
                    image_bytes = backend.generate(
                        title=pillow_title or prompt,
                        body=pillow_body,
                        theme=pillow_theme,
                        width=min(width, 1080),
                        height=min(height, 1080),
                    )
                else:
                    image_bytes = backend.generate(prompt, width=width, height=height)

                path = self._save_bytes(image_bytes, filename_prefix)
                logger.info(f"Imagem gerada via {name}: {path}")
                return {"success": True, "path": str(path), "caption": caption, "backend": name}

            except Exception as e:
                logger.warning(f"Backend {name} falhou: {e}")
                continue

        return {"success": False, "error": "Todos os backends falharam", "path": None}

    def _save_bytes(self, data: bytes, prefix: str) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        h = hashlib.md5(data[:256]).hexdigest()[:6]
        path = OUTPUT_DIR / f"{prefix}_{ts}_{h}.png"
        path.write_bytes(data)
        return path

    def _build_visual_prompt(self, topic: str, style: str) -> str:
        style_map = {
            "modern": "modern flat design, clean typography, vibrant colors, professional social media post",
            "cinematic": "cinematic 8k photography, dramatic lighting, bokeh background, ultra realistic",
            "minimal": "minimalist design, white space, elegant, simple geometric shapes",
            "vibrant": "vibrant neon colors, dynamic composition, energetic, trending on social media",
        }
        style_desc = style_map.get(style, style_map["modern"])
        return f"{topic}, {style_desc}, high quality, sharp details, 4k resolution"

    def _ai_caption(self, topic: str) -> str:
        """Gera legenda para o post usando Gemini."""
        if not self.gemini_key:
            return topic
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            prompt = (
                f"Crie uma legenda curta e engajante (máx 100 caracteres) para um post de "
                f"redes sociais sobre: {topic}. Retorne APENAS a legenda, sem explicações."
            )
            r = model.generate_content(prompt)
            return r.text.strip().strip('"')
        except Exception as e:
            logger.warning(f"Gemini caption falhou: {e}")
            return topic

    @staticmethod
    def _topic_to_theme(topic: str) -> str:
        topic_lower = topic.lower()
        if any(w in topic_lower for w in ["tech", "tecnologia", "ia", "software", "digital"]):
            return "tech"
        if any(w in topic_lower for w in ["nature", "natural", "verde", "sustentável", "eco"]):
            return "nature"
        if any(w in topic_lower for w in ["negócio", "business", "empresa", "vendas", "produto"]):
            return "business"
        if any(w in topic_lower for w in ["saúde", "health", "bem-estar", "fitness"]):
            return "health"
        return "default"


# ------------------------------------------------------------------ #
# CLI standalone
# ------------------------------------------------------------------ #

def main():
    import sys
    logging.basicConfig(level=logging.INFO)
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Inteligência Artificial revolucionando o futuro"
    print(f"Gerando post para: {topic}")
    gen = JarvisImageGenerator()
    result = gen.generate_social_post(topic)
    if result["success"]:
        print(f"Imagem salva em: {result['path']}")
        print(f"Legenda: {result['caption']}")
        print(f"Backend usado: {result['backend']}")
    else:
        print(f"Erro: {result['error']}")


if __name__ == "__main__":
    main()

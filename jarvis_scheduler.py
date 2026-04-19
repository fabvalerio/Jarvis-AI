#!/usr/bin/env python3
"""
Jarvis Scheduler - Agente de Cronogramas Inteligente com IA.

Cria cronogramas completos, planos de projeto, rotinas diárias e
calendários de conteúdo usando Gemini AI + armazenamento local.

Uso:
    sched = JarvisScheduler()

    # Cronograma em texto
    text = sched.create_schedule("semana de lançamento de produto SaaS")

    # Plano detalhado com tarefas
    plan = sched.create_project_plan("app mobile de delivery", weeks=4)

    # Rotina diária
    routine = sched.create_daily_routine("programador freelancer", wake_time="07:00")

    # Calendário de conteúdo para redes sociais
    calendar = sched.create_content_calendar("marca de moda sustentável", days=30)

    # Gera card visual do cronograma
    result = sched.create_visual_schedule("lançamento de produto", output_image=True)
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SCHEDULES_DIR = Path(os.getenv("SCHEDULES_DIR", "jarvis_schedules"))
SCHEDULES_DIR.mkdir(exist_ok=True)


class JarvisScheduler:
    """
    Agente de cronogramas com IA Gemini.
    Gera, salva e exporta cronogramas em múltiplos formatos.
    """

    SYSTEM_PROMPT = """Você é o Jarvis, assistente pessoal de IA especialista em planejamento e produtividade.
Crie cronogramas detalhados, realistas e acionáveis. Use emojis para organizar visualmente.
Formato: estruturado, com dias/horários/tarefas claros. Responda sempre em português do Brasil."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self._model = None

    def _get_model(self):
        if self._model:
            return self._model
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY não configurada no .env")
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=self.SYSTEM_PROMPT,
        )
        return self._model

    def _ask_ai(self, prompt: str) -> str:
        try:
            model = self._get_model()
            r = model.generate_content(prompt)
            return r.text.strip()
        except Exception as e:
            logger.error(f"Gemini erro: {e}")
            return f"Erro ao gerar cronograma: {e}"

    def _save(self, name: str, content: str, fmt: str = "txt") -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:40]
        path = SCHEDULES_DIR / f"{safe}_{ts}.{fmt}"
        path.write_text(content, encoding="utf-8")
        return path

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #

    def create_schedule(self, request: str, days: int = 7) -> str:
        """
        Cria um cronograma completo a partir de uma solicitação em linguagem natural.

        Args:
            request: Descrição do que precisa ser planejado
            days: Número de dias do cronograma (padrão: 7)

        Returns:
            Cronograma formatado em texto
        """
        today = datetime.now().strftime("%d/%m/%Y (%A)")
        prompt = f"""
Crie um cronograma completo e detalhado para os próximos {days} dias.

Pedido: {request}
Data de início: {today}

Inclua:
- Divisão por dias com datas reais
- Horários específicos para cada atividade
- Tarefas prioritárias destacadas
- Marcos importantes (milestones)
- Estimativas de tempo realistas
- Dicas práticas para execução

Formato esperado:
📅 DIA 1 - DD/MM/YYYY
  ⏰ 09:00 - Tarefa A (1h)
  ⏰ 10:00 - Tarefa B (30min)
  ...

Continue para todos os {days} dias.
"""
        result = self._ask_ai(prompt)
        self._save(f"cronograma_{request[:30]}", result)
        return result

    def create_project_plan(self, project: str, weeks: int = 4) -> str:
        """
        Cria um plano de projeto completo com fases, sprints e entregas.

        Args:
            project: Descrição do projeto
            weeks: Duração em semanas

        Returns:
            Plano estruturado em texto
        """
        prompt = f"""
Crie um plano de projeto profissional e detalhado.

Projeto: {project}
Duração: {weeks} semanas
Início: {datetime.now().strftime('%d/%m/%Y')}

Estruture com:
📋 VISÃO GERAL DO PROJETO
- Objetivo principal
- Resultados esperados
- KPIs de sucesso

🗓️ FASES DO PROJETO (divida em {weeks} semanas)
Para cada semana:
  - Meta da semana
  - Tarefas diárias específicas
  - Entregável da semana
  - Dependências e riscos

⚠️ RISCOS E MITIGAÇÕES
🔧 FERRAMENTAS RECOMENDADAS
📊 MÉTRICAS DE ACOMPANHAMENTO
✅ CHECKLIST FINAL
"""
        result = self._ask_ai(prompt)
        self._save(f"projeto_{project[:30]}", result)
        return result

    def create_daily_routine(self, profile: str, wake_time: str = "07:00",
                             sleep_time: str = "23:00", work_hours: int = 8) -> str:
        """
        Cria uma rotina diária otimizada com base no perfil do usuário.

        Args:
            profile: Perfil do usuário (ex: "programador freelancer", "empreendedor")
            wake_time: Horário de acordar
            sleep_time: Horário de dormir
            work_hours: Horas de trabalho por dia

        Returns:
            Rotina diária completa em texto
        """
        prompt = f"""
Crie uma rotina diária otimizada e produtiva para o perfil abaixo.

Perfil: {profile}
Horário acordar: {wake_time}
Horário dormir: {sleep_time}
Horas de trabalho: {work_hours}h/dia

Inclua:
🌅 ROTINA MATINAL (do acordar ao início do trabalho)
💼 BLOCO DE TRABALHO (com técnicas de foco, ex: Pomodoro)
🍽️ INTERVALOS E REFEIÇÕES
🏋️ EXERCÍCIO E SAÚDE
🧠 DESENVOLVIMENTO PESSOAL
🌙 ROTINA NOTURNA (encerramento do dia)

Para cada atividade:
- Horário exato
- Duração
- Dica de execução
- Por que essa atividade é importante para o perfil

Baseie-se em ciência da produtividade e ritmo circadiano.
"""
        result = self._ask_ai(prompt)
        self._save(f"rotina_{profile[:30]}", result)
        return result

    def create_content_calendar(self, brand: str, days: int = 30,
                                platforms: list = None) -> str:
        """
        Cria calendário de conteúdo para redes sociais.

        Args:
            brand: Descrição da marca/nicho
            days: Quantos dias de conteúdo
            platforms: Lista de plataformas (padrão: Instagram, TikTok, LinkedIn)

        Returns:
            Calendário de conteúdo estruturado
        """
        if platforms is None:
            platforms = ["Instagram", "TikTok", "LinkedIn"]
        plataformas = ", ".join(platforms)
        prompt = f"""
Crie um calendário editorial de conteúdo completo.

Marca/Nicho: {brand}
Período: {days} dias (a partir de {datetime.now().strftime('%d/%m/%Y')})
Plataformas: {plataformas}

Para cada semana, inclua:
📅 SEMANA X - Tema central

Para cada dia de postagem:
  📱 Plataforma
  🎯 Tipo de conteúdo (Reels, Carrossel, Story, Post estático, etc.)
  📝 Tema/Assunto específico
  💬 Chamada para ação (CTA)
  🏷️ Hashtags sugeridas (5-10)
  ⏰ Melhor horário para postar

Inclua:
- Variedade de formatos
- Mix de conteúdo (educativo, entretenimento, venda, bastidores)
- Datas comemorativas relevantes
- Sugestão de pautas para stories diários
"""
        result = self._ask_ai(prompt)
        self._save(f"calendario_{brand[:30]}", result)
        return result

    def create_study_plan(self, subject: str, goal: str,
                          available_hours_per_day: float = 2.0,
                          total_days: int = 30) -> str:
        """
        Cria plano de estudos personalizado.

        Args:
            subject: Assunto/habilidade a aprender
            goal: Objetivo ao final do período
            available_hours_per_day: Horas disponíveis por dia
            total_days: Total de dias do plano

        Returns:
            Plano de estudos detalhado
        """
        prompt = f"""
Crie um plano de estudos eficiente e progressivo.

Assunto: {subject}
Objetivo final: {goal}
Tempo disponível: {available_hours_per_day}h por dia
Duração: {total_days} dias

Estruture em 4 fases:
📚 FASE 1 - Fundamentos (25% do tempo)
🔧 FASE 2 - Prática (35% do tempo)
🚀 FASE 3 - Projetos (30% do tempo)
🏆 FASE 4 - Revisão e consolidação (10% do tempo)

Para cada semana:
- Tópicos a estudar (em ordem)
- Recursos recomendados (livros, cursos, sites - gratuitos e pagos)
- Exercícios práticos
- Projeto ou desafio semanal
- Checkpoint de avaliação

Técnicas de estudo recomendadas:
- Pomodoro, espaçamento, recuperação ativa, etc.

Inclua cronograma diário de exemplo para uma semana típica.
"""
        result = self._ask_ai(prompt)
        self._save(f"estudos_{subject[:30]}", result)
        return result

    def create_event_plan(self, event: str, event_date: str = None) -> str:
        """
        Cria plano completo de organização para um evento.

        Args:
            event: Descrição do evento
            event_date: Data do evento (DD/MM/YYYY), ou calcula automaticamente

        Returns:
            Plano de evento completo
        """
        if not event_date:
            event_date = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")
        days_until = (datetime.strptime(event_date, "%d/%m/%Y") - datetime.now()).days
        prompt = f"""
Crie um plano de organização completo para o evento abaixo.

Evento: {event}
Data do evento: {event_date}
Dias até o evento: {days_until}

Organize em linha do tempo reversa (da data do evento para hoje):

Para cada etapa/semana:
📋 O que fazer
👥 Responsáveis (categorias)
💰 Estimativa de custo
⚠️ Pontos de atenção
✅ Checklist específico

Inclua:
- Contratações e fornecedores necessários
- Comunicação e divulgação
- Logística e infraestrutura
- Plano B para imprevistos
- Checklist do dia do evento
- Pós-evento (agradecimentos, relatório, etc.)
"""
        result = self._ask_ai(prompt)
        self._save(f"evento_{event[:30]}", result)
        return result

    def create_visual_schedule(self, request: str, output_image: bool = False) -> dict:
        """
        Cria cronograma e opcionalmente gera card visual.

        Returns:
            dict com keys: text (cronograma), image_path (se output_image=True)
        """
        text = self.create_schedule(request)
        result = {"text": text, "image_path": None}

        if output_image:
            try:
                from jarvis_image_generator import JarvisImageGenerator
                gen = JarvisImageGenerator()
                img_result = gen.generate_schedule_card(
                    schedule_text=text[:600],
                    title=f"Cronograma: {request[:40]}"
                )
                if img_result["success"]:
                    result["image_path"] = img_result["path"]
            except Exception as e:
                logger.warning(f"Imagem do cronograma falhou: {e}")

        return result

    def list_saved_schedules(self) -> list:
        """Lista todos os cronogramas salvos."""
        files = sorted(SCHEDULES_DIR.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
        return [
            {
                "name": f.stem,
                "path": str(f),
                "created": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
                "size_kb": round(f.stat().st_size / 1024, 1),
            }
            for f in files
        ]

    def get_schedule(self, path: str) -> str:
        """Lê um cronograma salvo pelo caminho."""
        return Path(path).read_text(encoding="utf-8")

    def quick_plan(self, goal: str) -> str:
        """
        Gera um plano rápido de ação (5 próximas tarefas prioritárias).
        Útil para chamadas rápidas pelo WhatsApp ou voz.
        """
        prompt = f"""
Crie um plano de ação RÁPIDO com exatamente 5 próximas ações prioritárias.

Objetivo: {goal}

Formato EXATO (curto e direto):
PLANO DE AÇÃO: {goal}

1. [Ação imediata - fazer HOJE]
2. [Ação importante - fazer amanhã]
3. [Ação estratégica - essa semana]
4. [Ação de médio prazo - próximas 2 semanas]
5. [Ação de longo prazo - próximo mês]

DICA PRINCIPAL: [uma dica crucial para executar esse plano]

Seja específico, acionável e realista. Máximo 150 palavras no total.
"""
        return self._ask_ai(prompt)


# ------------------------------------------------------------------ #
# CLI standalone
# ------------------------------------------------------------------ #

def main():
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Uso: python jarvis_scheduler.py <tipo> <pedido>")
        print("Tipos: cronograma | projeto | rotina | conteudo | estudos | evento | rapido")
        print('\nExemplo: python jarvis_scheduler.py cronograma "semana de lançamento de app"')
        return

    tipo = sys.argv[1]
    pedido = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "plano geral de produtividade"

    sched = JarvisScheduler()
    print(f"\nGerando {tipo} para: {pedido}\n")
    print("=" * 60)

    if tipo == "cronograma":
        print(sched.create_schedule(pedido))
    elif tipo == "projeto":
        print(sched.create_project_plan(pedido))
    elif tipo == "rotina":
        print(sched.create_daily_routine(pedido))
    elif tipo == "conteudo":
        print(sched.create_content_calendar(pedido))
    elif tipo == "estudos":
        print(sched.create_study_plan(pedido, goal="dominar o assunto"))
    elif tipo == "evento":
        print(sched.create_event_plan(pedido))
    elif tipo == "rapido":
        print(sched.quick_plan(pedido))
    else:
        print(f"Tipo desconhecido: {tipo}")


if __name__ == "__main__":
    main()

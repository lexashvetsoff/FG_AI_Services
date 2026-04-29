from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.competitor_analysis import LLMReport
from app.ai.competitor_alnalysis.llm import AnalystClient
from app.services.competitor_alnalysis.prompt_builder import PromptBuilder
from app.services.competitor_alnalysis.context_builder import ContextBuilder


class LLMService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.context_builder = ContextBuilder(session)
        self.prompt_builder = PromptBuilder()
        self.client = AnalystClient(settings.ANALYST_OLLAMA_HOST)
    
    async def generate_report(self, import_id: str):
        # 1. собрать контекст
        context = await self.context_builder.build(import_id)

        # 2. собрать prompt
        prompt = self.prompt_builder.build(context)

        # 3. запрос к LLM
        response = await self.client.generate(prompt)

        # 4. сохранить
        await self._save(import_id, response)

        return response
    
    async def _save(self, import_id: str, content: str):
        stmt = insert(LLMReport).values(
            import_id=import_id,
            report_type='summary',
            content=content
        )

        await self.session.execute(stmt)
        await self.session.commit()

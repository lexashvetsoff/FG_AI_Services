from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.utils.markdown import md_to_html
from app.models.competitor_analysis import LLMReport
from app.ai.competitor_alnalysis.llm import AnalystClient
from app.services.competitor_alnalysis.prompt_builder import PromptBuilder
from app.services.competitor_alnalysis.context_builder import ContextBuilder


ETALON_SORTING_REPORTS = [
    "0-150", "151-500", "501-1000", "1001-1500", "1501-2000", "2001-2500", "2501-3000", "3001-5000", "5000+"
]


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
    
    async def generate_reports(self, import_id: str):
        segments = await self.context_builder.get_segments(import_id)
        reports = []

        for segment in segments:
            context = await self.context_builder.build(import_id, segment)
            prompt = self.prompt_builder.build(context)

            response = await self.client.generate(prompt)
            html_text = md_to_html(response)

            reports.append({
                'segment': segment,
                'report': response,
                'html': html_text
            })

            await self._save(import_id, response, 'report_segment')

        # Отсортируем по ценовым сегментам
        order_map = {seg: idx for idx, seg in enumerate(ETALON_SORTING_REPORTS)}
        sortered_reports = sorted(reports, key=lambda item: order_map[item['segment']])
        
        # return reports
        return sortered_reports
    
    async def generate_summary_report(self, import_id: str, segment_reports: list):
        prompt = self.prompt_builder.build_summary(segment_reports)
        response = await self.client.generate(prompt)
        html_text = md_to_html(response)
        report = {
            'report': response,
            'html': html_text
        }
        await self._save(import_id, response, 'summary')
        return report
    
    async def _save(self, import_id: str, content: str, report_type: str = 'summary'):
        stmt = insert(LLMReport).values(
            import_id=import_id,
            report_type=report_type,
            content=content
        )

        await self.session.execute(stmt)
        await self.session.commit()

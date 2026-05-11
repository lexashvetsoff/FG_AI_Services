import logging
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.utils.markdown import md_to_html
from app.utils.sql_validator import validate_sql
from app.utils.sql_guard import enforce_import_filter
from app.schemas.schemas import ChatContextExtra
from app.services.competitor_alnalysis.sql_executor import execute_sql
from app.models.competitor_analysis import LLMReport
from app.ai.competitor_alnalysis.llm import AnalystClient
from app.services.competitor_alnalysis.prompt_builder import PromptBuilder
from app.services.competitor_alnalysis.context_builder import ContextBuilder
from app.services.competitor_alnalysis.chat_router import ChatRouter


ETALON_SORTING_REPORTS = [
    "0-150", "151-500", "501-1000", "1001-1500", "1501-2000", "2001-2500", "2501-3000", "3001-5000", "5000+"
]


class LLMService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.context_builder = ContextBuilder(session)
        self.prompt_builder = PromptBuilder()
        self.client = AnalystClient(settings.ANALYST_OLLAMA_HOST)
        self.router = ChatRouter()
    
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
    
    async def generate_reports(self, session: AsyncSession, import_id: str):
        reports = []

        result = await session.execute(
            select(LLMReport)
            .where(
                LLMReport.import_id == import_id,
                LLMReport.report_type == 'report_segment'
            )
        )
        reports_in_db = result.scalars().all()

        if reports_in_db:
            logging.info(f'(generate_reports) Нашли в базе отчеты по import_id: {import_id}')
            for r in reports_in_db:
                reports.append({
                    'segment': r.price_segment,
                    'report': r.content,
                    'html': md_to_html(r.content)
                })
        else:
            logging.info(f'(generate_reports) НЕ нашли в базе отчеты по import_id: {import_id} - генерируем')
            segments = await self.context_builder.get_segments(import_id)
            for segment in segments:
                # context = await self.context_builder.build(import_id, segment)
                # prompt = self.prompt_builder.build(context)
                context = await self.context_builder.build_for_segment(import_id, segment)
                prompt = self.prompt_builder.build_segment_prompt(context)

                response = await self.client.generate(prompt)
                html_text = md_to_html(response)

                reports.append({
                    'segment': segment,
                    'report': response,
                    'html': html_text
                })

                await self._save(import_id, response, 'report_segment', segment)

        # Отсортируем по ценовым сегментам
        order_map = {seg: idx for idx, seg in enumerate(ETALON_SORTING_REPORTS)}
        sortered_reports = sorted(reports, key=lambda item: order_map[item['segment']])
        
        # return reports
        return sortered_reports
    
    async def generate_summary_report(self, session: AsyncSession, import_id: str, segment_reports: list):
        result = await session.execute(
            select(LLMReport)
            .where(
                LLMReport.import_id == import_id,
                LLMReport.report_type == 'summary'
            )
            .limit(1)
        )
        report_in_db = result.scalar()

        if report_in_db:
            logging.info(f'(generate_summary_report) Нашли в базе отчет по import_id: {import_id}')
            report = {
                'report': report_in_db.content,
                'html': md_to_html(report_in_db.content)
            }
        else:
            logging.info(f'(generate_summary_report) НЕ нашли в базе отчеты по import_id: {import_id} - генерируем')
            prompt = self.prompt_builder.build_summary(segment_reports)
            response = await self.client.generate(prompt)
            html_text = md_to_html(response)
            report = {
                'report': response,
                'html': html_text
            }
            await self._save(import_id, response, 'summary', None)
        return report
    
    async def _save(self, import_id: str, content: str, report_type: str = 'summary', price_segment: str = None):
        stmt = insert(LLMReport).values(
            import_id=import_id,
            report_type=report_type,
            content=content,
            price_segment=price_segment
        )

        await self.session.execute(stmt)
        await self.session.commit()
    
    async def chat(self, import_id: str, question: str, extra: ChatContextExtra = None):
        # mode = self.router.detect_mode(question)

        # # 1. АНАЛИТИКА (основной режим)
        # if mode == 'context':
        #     context = await self.context_builder.build_full(import_id)
        #     prompt = self.prompt_builder.build_chat_prompt(question, context)

        #     response = await self.client.generate(prompt)
        #     html_text = md_to_html(response)
        #     return html_text

        # # 2. SQL режим
        # if mode == 'sql':
        #     response = await self.answer_with_sql(import_id, question)
        #     html_text = md_to_html(response)
        #     return html_text

        # response = await self.answer_with_sql(import_id, question)
        # html_text = md_to_html(response)
        # return html_text
        if extra:
            logging.info(f'Generate chat context')

            context = await self.context_builder.build_chat_context(
                import_id=import_id,
                our_pharmacy=extra.our_pharmacy,
                comp_pharmacy=extra.competitor_pharmacy,
                segment=extra.segment
            )
            prompt = self.prompt_builder.build_answer_prompt(question, context)
            response = await self.client.generate(prompt)
            html_text = md_to_html(response)
            return html_text
        
        else:
            mode = self.router.detect_mode(question)
            if mode == 'context':
                prompt = self.prompt_builder.build_over_prompt(question)
                response = await self.client.generate(prompt)
                html_text = md_to_html(response)
                return html_text
            if mode == 'sql':
                response = await self.answer_with_sql(import_id, question)
                html_text = md_to_html(response)
                return html_text
    
    async def answer_question(self, import_id: str, question: str):
        context = await self.context_builder.build_chat(import_id)
        prompt = self.prompt_builder.build_chat_prompt(question, context)
        response = await self.client.generate(prompt)
        return response
    
    async def answer_with_sql(self, import_id: str, question: str):
        # 1. генерим SQL
        sql_prompt = self.prompt_builder.build_sql_propmt(question, import_id)
        sql = await self.client.generate(sql_prompt)

        # 2. чистим ответ
        sql = sql.strip().replace("```sql", "").replace("```", "")

        # 3. валидация
        if not validate_sql(sql, import_id):
            # 3.1 Пробуем принудительно добавить фильтр по import_id и проверить еще раз
            sql = enforce_import_filter(sql, import_id)
        if not validate_sql(sql, import_id):
            return f'Ошибка: сгенерирован небезопасный SQL: {sql}'
        
        logging.info(sql)
        # 4. выполнение
        data = await execute_sql(self.session, sql)

        # 5. объяснение
        answer_prompt = self.prompt_builder.build_answer_prompt(question, data)
        answer = await self.client.generate(answer_prompt)

        return answer

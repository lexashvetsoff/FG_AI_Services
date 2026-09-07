import logging

from app.config import settings
from app.ai.property_extractor.llm import LLMExtractor
from app.schemas.schemas import ExtractData, ExtractRequest


logger = logging.getLogger(__name__)


class ExtractService:
    def __init__(self):
        self.extractor = LLMExtractor()

    async def process(self, request: ExtractRequest) -> ExtractData | None:
        return await self.extractor.extract(request=request)

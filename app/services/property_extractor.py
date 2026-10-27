import logging

from app.config import settings
from app.ai.property_extractor.llm import (
    LLMExtractor, 
    LLMClassExtractor, 
    LLMClassifier,
    LLMClassifierMNN,
    LLMClassifyreDoza
)
from app.schemas.schemas import (
    ExtractData, 
    ExtractRequest,
    ClassifyAndExtractRequest,
    ClassifyAndExtractResponse,
    ClassifyRequest,
    MNNClassifyRequest,
    DosageCleanRequest,
    DosageCleanResponse
)


logger = logging.getLogger(__name__)


class ExtractService:
    def __init__(self):
        self.extractor = LLMExtractor()

    async def process(self, request: ExtractRequest) -> ExtractData | None:
        return await self.extractor.extract(request=request)


class ClassExtractService:
    def __init__(self):
        self.extractor = LLMClassExtractor()

    async def process(self, request: ClassifyAndExtractRequest):
        return await self.extractor.process(request=request)


class ClassifyerService:
    def __init__(self):
        self.classifyer = LLMClassifier()

    async def process(self, request: ClassifyRequest):
        return await self.classifyer.process(request)


class ClassifyerMNNService:
    def __init__(self):
        self.classifyer = LLMClassifierMNN()

    async def process(self, request: MNNClassifyRequest):
        return await self.classifyer.process(request)


class ClassifyerDozaService:
    def __init__(self):
        self.classifyer = LLMClassifyreDoza()

    async def process(self, request: DosageCleanRequest):
        return await self.classifyer.process(request)

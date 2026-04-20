import uuid
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


class PharmaSpecs(BaseModel):
    mnn: Optional[str] = Field(None, max_length=150)
    strength: Optional[str] = Field(None, max_length=50)
    dosage_form: Optional[str] = Field(None, max_length=100)
    pack_size: Optional[str] = Field(None, max_length=50)
    manufacturer: Optional[str] = Field(None, max_length=150)
    product_type: Optional[str] = Field(None, max_length=50)


class MatchRequest(BaseModel):
    internal_name: str = Field(..., min_length=3, max_length=300)
    competitor_names: List[str] = Field(..., min_length=2, max_length=20)
    internal_id: Optional[str] = Field(None, max_length=100)
    request_id: Optional[str] = Field(default_factory=lambda: f'req_{uuid.uuid4().hex[:8]}')
    category: Optional[str] = Field(None, max_length=100)
    pharma_specs: Optional[PharmaSpecs] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "internal_name": "Ибупрофен 400 мг таблетки п/о №20",
                "competitor_names": ["Ибупрофен-Акрихин 400мг таб.п.о. 20шт", "Ибупрофен 200мг №30 таблетки"],
                "internal_id": "271162",
                "pharma_specs": {"mnn": "Ибупрофен", "strength": "400 мг", "dosage_form": "таблетки", "product_type": "Лекарственный препарат"}
            }
        }
    )


class MatchResponse(BaseModel):
    internal_id: Optional[str]
    request_id: str
    internal_name: str
    best_match: Optional[str]
    confidence: float
    reasoning: str
    source: str
    all_scores: Dict[str, float]


class TokenRequest(BaseModel):
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expire_in: int

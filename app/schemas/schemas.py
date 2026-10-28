import uuid
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Union, Any


class PharmaSpecs(BaseModel):
    mnn: Optional[str] = Field(None, max_length=150)
    strength: Optional[str] = Field(None, max_length=50)
    dosage_form: Optional[str] = Field(None, max_length=100)
    pack_size: Optional[str] = Field(None, max_length=50)
    manufacturer: Optional[str] = Field(None, max_length=150)
    product_type: Optional[str] = Field(None, max_length=50)


class MatchRequest(BaseModel):
    internal_name: str = Field(..., min_length=3, max_length=300)
    competitor_names: List[str] = Field(..., min_length=1, max_length=40)
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


class ChatRequest(BaseModel):
    import_id: str
    question: str


class ChatContextExtra(BaseModel):
    our_pharmacy: str
    competitor_pharmacy: str
    segment: str


class ChatRequestContext(BaseModel):
    import_id: str
    question: str
    extra: ChatContextExtra


class ExtractData(BaseModel):
    name: str = Field(default="", description="Торговое наименование продукта")
    brand: str = Field(default="", description="Бренд продукта")
    type: List[str] = Field(default_factory=list, description="Тип продукта")
    taste: List[str] = Field(default_factory=list, description="Вкус")
    color: List[str] = Field(default_factory=list, description="Цвет")
    aroma: List[str] = Field(default_factory=list, description="Аромат")
    effect: List[str] = Field(default_factory=list, description="Эффекты")
    result: List[str] = Field(default_factory=list, description="Результаты")
    component: List[str] = Field(default_factory=list, description="Компоненты/Состав")
    hardness: List[str] = Field(default_factory=list, description="Жесткость")
    feature: List[str] = Field(default_factory=list, description="Особенности")


class ExtractRequest(BaseModel):
     text: str = Field(..., description="Сырой текст для извлечения данных")


class ExtractResponse(BaseModel):
    status: str
    data: ExtractData


class CategorySchema(BaseModel):
    """Описание одной категории и её свойств"""
    name: str = Field(..., description="Название категории")
    properties: List[str] = Field(..., description="Список свойств для извлечения")


class TextItem(BaseModel):
    """Единица текста с идентификатором"""
    id: str = Field(..., description="Уникальный идентификатор текста (например, SKU или UUID)")
    text: str = Field(..., description="Сырой текст (описание, наименование) для анализа")


class ClassifyAndExtractRequest(BaseModel):
    """Тело запроса: список текстов с ID и общие категории"""
    items: List[TextItem] = Field(
        ..., 
        description="Список текстов с идентификаторами для анализа",
        min_length=1
    )
    categories: List[CategorySchema] = Field(..., description="Список возможных категорий с их свойствами")


class ExtractedProperty(BaseModel):
    """Одно извлеченное свойство"""
    property_name: str = Field(..., description="Название свойства")
    value: Union[str, int, float, List[str]] = Field(..., description="Извлеченное значение")


class SingleTextResult(BaseModel):
    """Результат обработки одного текста"""
    id: str = Field(..., description="Идентификатор исходного текста (из запроса)")
    category: Optional[str] = Field(None, description="Найденная категория. Null, если не найдено.")
    confidence: Optional[float] = Field(None, description="Уверенность модели (0.0 - 1.0)")
    extracted_properties: List[ExtractedProperty] = Field(default_factory=list, description="Список извлеченных свойств")
    error: Optional[str] = Field(None, description="Текст ошибки, если для этого конкретного текста не удалось получить результат")


class ClassifyAndExtractResponse(BaseModel):
    """Итоговое тело ответа API"""
    status: str = Field(default="success", description="Общий статус выполнения")
    results: List[SingleTextResult] = Field(..., description="Список результатов для каждого переданного текста")


class ProductItem(BaseModel):
    code: Union[int, str] = Field(..., description="Код товара")
    text: str = Field(..., description="Наименование товара")


class AllowedValue(BaseModel):
    code: str = Field(..., description="Код значения")
    values: List[str] = Field(..., description="Список вариантов наименования значения")


class ClassificationDimension(BaseModel):
    """
    Зафиксируем id:
    dim_form - формы выпуска
    dim_method - способы применения
    dim_doz - дозировки
    """
    id: str = Field(..., description="ID свойства")
    name: str = Field(..., description="Наименование свойства")
    is_multi_value: bool = Field(
        default=False, 
        description="Может ли измерение иметь несколько значений (True - всегда возвращать список, False - строку или null)"
    )
    allowed_values: List[AllowedValue] = Field(..., description="Массив допустимых значений с кодами")


class ClassifyRequest(BaseModel):
    products: List[ProductItem] = Field(..., min_length=1)
    dimensions: List[ClassificationDimension] = Field(..., min_length=1)


class ProductClassification(BaseModel):
    code: Union[int, str] = Field(..., description="Код товара из запроса")
    reasoning: Optional[str] = Field(None, description="Рассуждение модели: расшифровка аббревиатур и логика выбора кодов")
    # Значение может быть строкой, списком строк или null
    classifications: Dict[str, Any] = Field(..., description="Результаты классификации")


class ClassifyResponse(BaseModel):
    status: str = 'success'
    results: List[ProductClassification]


class MNNProductItem(BaseModel):
    code: str = Field(..., description="Код")
    text: str = Field(..., description="Текстовое наименование для классификации")


class MNNDictionaryItem(BaseModel):
    code: str = Field(..., description="Код МННН")
    value: str = Field(..., description="Нименование МНН")


class MNNClassifyRequest(BaseModel):
    products: List[MNNProductItem] = Field(..., min_length=1)
    dictionary: List[MNNDictionaryItem] = Field(..., min_length=1)


class MNNClassifyResult(BaseModel):
    code: str = Field(..., description="Код из запроса")
    mnn_code: Optional[str] = Field(None, description="Код МНН из справочника")
    reasoning: Optional[str] = Field(None, description="Рассуждения модели")


class MNNClassifyResponse(BaseModel):
    status: str = "success"
    results: List[MNNClassifyResult]


class DosageItem(BaseModel):
    original_text: str
    normalized_text: str
    group: str
    is_garbage: bool = False
    comment: Optional[str] = None


class DosageCleanRequest(BaseModel):
    dosages: List[str] = Field(..., min_length=1)


class DosageCleanResponse(BaseModel):
    status: str = "success"
    total_items: int
    garbage_count: int
    # groups_summary: dict
    results: List[DosageItem]

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    DateTime,
    Enum,
    BigInteger,
    Integer,
    ForeignKey,
    JSON,
    Boolean,
    Numeric,
    Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.competitor_analysis_utils import SourceType, ImportStatus


class Import(Base):
    __tablename__ = 'imports'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # relationships
    raw_data: Mapped[List['RawData']] = relationship(back_populates='import_obj')
    prices: Mapped[List['NormalizedPrice']] = relationship(back_populates='import_obj')


class RawData(Base):
    __tablename__ = 'raw_data'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('imports.id'))
    sheet_name: Mapped[Optional[str]] = mapped_column(String)
    row_index: Mapped[Optional[int]] = mapped_column(Integer)
    data: Mapped[Dict[str, Any]] = mapped_column(JSON)
    import_obj: Mapped['Import'] = relationship(back_populates='raw_data')


class NormalizedPrice(Base):
    __tablename__ = 'normalized_prices'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('imports.id'), index=True)
    city: Mapped[str] = mapped_column(String, index=True)
    product_name: Mapped[str] = mapped_column(String, index=True)
    pharmacy_name: Mapped[str] = mapped_column(String, index=True)
    is_our: Mapped[bool] = mapped_column(Boolean)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    purchase_price: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    import_obj: Mapped['Import'] = relationship(back_populates='prices')


class ProductMetrics(Base):
    __tablename__ = 'product_metrics'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('imports.id'), index=True)
    city: Mapped[str] = mapped_column(String, index=True)
    product_name: Mapped[str] = mapped_column(String, index=True)
    avg_price: Mapped[Decimal] = mapped_column(Numeric)
    min_price: Mapped[Decimal] = mapped_column(Numeric)
    max_price: Mapped[Decimal] = mapped_column(Numeric)
    std_dev: Mapped[Decimal] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class CompetitorMetrics(Base):
    __tablename__ = 'competitor_metrics'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('imports.id'), index=True)
    city: Mapped[str] = mapped_column(String, index=True)
    pharmacy_name: Mapped[str] = mapped_column(String, index=True)
    price_index: Mapped[Decimal] = mapped_column(Numeric)
    category: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class CityMetrics(Base):
    __tablename__ = 'city_metrics'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('imports.id'), index=True)
    city: Mapped[str] = mapped_column(String, index=True)
    avg_price: Mapped[Decimal] = mapped_column(Numeric)
    price_dispersion: Mapped[Decimal] = mapped_column(Numeric)
    avg_discount: Mapped[Decimal] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class LLMReport(Base):
    __tablename__ = 'llm_reports'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('imports.id'), index=True)
    report_type: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

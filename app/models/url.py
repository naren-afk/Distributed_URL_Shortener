from datetime import datetime
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Index, Integer, String, Text, func
from app.core.database import Base


class URL(Base):
    __tablename__ = "urls"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    short_code = Column(String(32), unique=True, index=True, nullable=False)
    original_url = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    click_count = Column(BigInteger, default=0, nullable=False)

    __table_args__ = (
        Index("idx_urls_short_code_active", "short_code", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<URL id={self.id} code={self.short_code} url={self.original_url[:30]}>"

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, Text, func
from app.core.database import Base


class ClickEvent(Base):
    __tablename__ = "click_events"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    short_code = Column(String(32), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    referrer = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    browser = Column(String(64), nullable=True)
    os = Column(String(64), nullable=True)
    country = Column(String(64), nullable=True)

    __table_args__ = (
        Index("idx_click_events_code_time", "short_code", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<ClickEvent code={self.short_code} time={self.timestamp}>"

from sqlalchemy import Column, String, LargeBinary, DateTime, Text
from datetime import datetime
from app.database import Base


class TemplatePreview(Base):
    __tablename__ = "template_previews"

    template_id = Column(String, primary_key=True)
    image_data = Column(LargeBinary, nullable=False)
    content_type = Column(String, default="image/png")
    revised_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

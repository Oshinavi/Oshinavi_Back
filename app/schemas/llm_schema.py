from pydantic import BaseModel
from typing  import Optional

class TranslationResult(BaseModel):
    translated: str
    category:   str
    start:      Optional[str] = None
    end:        Optional[str] = None

class ReplyResult(BaseModel):
    reply_text: str
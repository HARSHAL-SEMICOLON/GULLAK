from pydantic import BaseModel
from typing import Optional
from datetime import date as dt_date, time as dt_time

class Profile(BaseModel):
    id: Optional[str] = None
    name: str
    avatar_emoji: str = "👤"
    created_at: Optional[str] = None

class Transaction(BaseModel):
    id: str
    date: dt_date
    time: dt_time
    day_of_week: str
    merchant_raw: str
    merchant_clean: str
    merchant_type: str
    amount: float
    transaction_type: str  # 'debit' | 'credit'
    payment_mode: str
    bank: str
    upi_ref: str
    category: str
    user_label: Optional[str] = None
    macro_category: str
    confidence: float
    flag: Optional[str] = None
    is_recurring: bool = False
    month: str  # "YYYY-MM"
    regret_status: Optional[str] = None  # "worth_it", "regret", "neutral"
    profile_id: Optional[str] = None

class Goal(BaseModel):
    id: Optional[str] = None
    name: str
    target_amount: float
    current_amount: float = 0.0
    deadline: Optional[dt_date] = None
    profile_id: Optional[str] = None

class Budget(BaseModel):
    id: Optional[str] = None
    category: str
    target_amount: float
    spent_amount: float = 0.0
    month: str
    profile_id: Optional[str] = None

class DailyLogRequest(BaseModel):
    item_name: str
    category: str
    amount: float
    date: Optional[str] = None
    profile_id: Optional[str] = None

class ChatRequest(BaseModel):
    query: str

class RegretUpdateRequest(BaseModel):
    regret_status: str  # "worth_it", "regret", "neutral"

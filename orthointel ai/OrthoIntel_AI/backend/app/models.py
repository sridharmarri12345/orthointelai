from pydantic import BaseModel, Field
from typing import Optional, Literal

class ReviewInput(BaseModel):
    review: str = Field(min_length=5, max_length=5000)
    product: str = "Unspecified"
    region: str = "Unknown"
    source: str = "Manual"
    rating: Optional[float] = Field(default=None, ge=1, le=5)

class CompetitorInput(BaseModel):
    competitor: str = Field(min_length=1, max_length=100)
    product: str
    region: str
    status: Literal["In stock", "Low stock", "Out of stock", "Delayed"]

class TicketInput(BaseModel):
    product: str
    issue: str
    recommendation: str
    priority: Literal["Low", "Medium", "High", "Critical"] = "Medium"

class TicketStatusInput(BaseModel):
    status: Literal["Open", "Under Review", "Approved", "In Progress", "Resolved", "Rejected"]

class MarginInput(BaseModel):
    mrp: float = Field(gt=0)
    base_cost: float = Field(gt=0)
    retailer_margin_pct: float = Field(ge=0, le=80)
    proposed_trade_margin_pct: float = Field(ge=0, le=80)
    minimum_company_margin_pct: float = Field(default=10, ge=0, le=80)

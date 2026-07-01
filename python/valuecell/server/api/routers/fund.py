"""Fund API routes — manage user-tracked mutual funds and their analysis."""

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Path

from valuecell.server.db.repositories.fund_repository import get_fund_repository
from valuecell.server.services.fund_analysis import FundAnalysisService

from .watchlist import DEFAULT_USER_ID
from ..schemas.base import SuccessResponse

router = APIRouter(prefix="/fund", tags=["Fund"])
fund_repo = get_fund_repository()
fund_analysis_svc = FundAnalysisService()


# ── Request Schemas ───────────────────────────────────────────────────


class CreateFundRequest(BaseModel):
    name: str
    code: str | None = None


class AddHoldingRequest(BaseModel):
    ticker: str
    name: str | None = None
    weight: float = 0.0


# ── Routes ────────────────────────────────────────────────────────────


@router.post("/", response_model=SuccessResponse)
async def create_fund(body: CreateFundRequest):
    """Create a new fund for the default user."""
    fund = fund_repo.create_fund(
        user_id=DEFAULT_USER_ID, name=body.name, code=body.code
    )
    if not fund:
        raise HTTPException(400, detail="Failed to create fund")
    return SuccessResponse.create(data=fund.to_dict(), msg="Fund created")


@router.get("/", response_model=SuccessResponse)
async def list_funds():
    """Get all funds for the default user."""
    funds = fund_repo.get_user_funds(DEFAULT_USER_ID)
    return SuccessResponse.create(
        data=[f.to_dict() for f in funds], msg=f"Found {len(funds)} funds"
    )


@router.get("/{fund_id}", response_model=SuccessResponse)
async def get_fund(fund_id: int = Path(..., description="Fund ID")):
    """Get a specific fund by ID."""
    fund = fund_repo.get_fund(fund_id, DEFAULT_USER_ID)
    if not fund:
        raise HTTPException(404, detail="Fund not found")
    holdings = fund_repo.get_fund_holdings(fund_id)
    data = fund.to_dict()
    data["holdings"] = [h.to_dict() for h in holdings]
    return SuccessResponse.create(data=data, msg="Fund retrieved")


@router.delete("/{fund_id}", response_model=SuccessResponse)
async def delete_fund(fund_id: int = Path(..., description="Fund ID")):
    """Delete a fund and all its holdings."""
    ok = fund_repo.delete_fund(fund_id, DEFAULT_USER_ID)
    if not ok:
        raise HTTPException(404, detail="Fund not found")
    return SuccessResponse.create(msg="Fund deleted")


@router.post("/{fund_id}/holdings", response_model=SuccessResponse)
async def add_holding(
    body: AddHoldingRequest,
    fund_id: int = Path(..., description="Fund ID"),
):
    """Add a stock holding to a fund."""
    fund = fund_repo.get_fund(fund_id, DEFAULT_USER_ID)
    if not fund:
        raise HTTPException(404, detail="Fund not found")
    holding = fund_repo.add_holding(
        fund_id=fund_id, ticker=body.ticker, name=body.name, weight=body.weight
    )
    if not holding:
        raise HTTPException(400, detail="Failed to add holding")
    return SuccessResponse.create(data=holding.to_dict(), msg="Holding added")


@router.delete("/{fund_id}/holdings/{ticker}", response_model=SuccessResponse)
async def remove_holding(
    ticker: str,
    fund_id: int = Path(..., description="Fund ID"),
):
    """Remove a holding from a fund."""
    ok = fund_repo.remove_holding(fund_id, ticker)
    if not ok:
        raise HTTPException(404, detail="Holding not found")
    return SuccessResponse.create(msg="Holding removed")


@router.get("/{fund_id}/analysis", response_model=SuccessResponse)
async def analyze_fund(fund_id: int = Path(..., description="Fund ID")):
    """Run a comprehensive analysis on a fund by scoring its holdings."""
    fund = fund_repo.get_fund(fund_id, DEFAULT_USER_ID)
    if not fund:
        raise HTTPException(404, detail="Fund not found")
    holdings = fund_repo.get_fund_holdings(fund_id)
    if not holdings:
        raise HTTPException(400, detail="Fund has no holdings to analyze")

    result = await fund_analysis_svc.analyze_fund(fund, holdings)
    return SuccessResponse.create(
        data=result.model_dump(), msg="Fund analysis complete"
    )

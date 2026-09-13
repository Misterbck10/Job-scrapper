from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.domain.models import Search

router = APIRouter()


class SearchCreate(BaseModel):
    name: str
    query: dict
    country_code: str | None = None


class SearchOut(BaseModel):
    id: UUID
    name: str
    query: dict
    country_code: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/searches", status_code=201, response_model=SearchOut)
async def create_search(body: SearchCreate, session: AsyncSession = Depends(get_session)) -> Search:
    search = Search(name=body.name, query=body.query, country_code=body.country_code)
    session.add(search)
    await session.commit()
    await session.refresh(search)
    return search

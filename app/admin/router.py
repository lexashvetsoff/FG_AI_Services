from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.api.dependencies import get_db, require_admin
from app.core.templates import templates
from app.models.user import User


router = APIRouter(prefix='/admin', tags=['AdminUI'])


@router.get('/', response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    return templates.TemplateResponse(
        '/admin/dashboard.html',
        {
            'request': request,
            'user': user,
        }
    )

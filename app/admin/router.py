from enum import Enum
from fastapi import APIRouter, Depends, Request, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.api.dependencies import get_db, require_admin
from app.core.security import hash_password
from app.core.templates import templates
from app.models.user import User


router = APIRouter(prefix='/admin', tags=['AdminUI'])


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"


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


@router.get('/users', response_class=HTMLResponse)
async def admin_users_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()

    return templates.TemplateResponse(
        '/admin/users/list.html',
        {
            'request': request,
            'user': user,
            'users': users
        }
    )


@router.post('/users/{user_id}/toggle')
async def admin_toggle_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()

    if not target:
        raise HTTPException(status_code=404, detail='User not found')
    
    target.is_active = not target.is_active
    await db.commit()

    return RedirectResponse(
        url='/admin/users',
        status_code=status.HTTP_302_FOUND
    )


@router.get('/users/create', response_class=HTMLResponse)
async def admin_user_create_page(
    request: Request,
    admin: User = Depends(require_admin)
):
    return templates.TemplateResponse(
        '/admin/users/create.html',
        {
            'request': request,
            'user': admin
        }
    )


@router.post('/users/create')
async def admin_user_create(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    # проверка уникальности email
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        return templates.TemplateResponse(
            '/admin/users/create.html',
            {
                'request': request,
                'error': 'User with this email already exists'
            },
            status_code=400
        )
    
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=UserRole(role).value,
        is_active=True
    )
    db.add(user)
    await db.commit()

    return RedirectResponse(
        url='/admin/users',
        status_code=status.HTTP_302_FOUND
    )

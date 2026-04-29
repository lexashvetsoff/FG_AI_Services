import os
import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, Request, UploadFile, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.config import settings
from app.api.dependencies import get_db, get_current_user
from app.core.templates import templates
from app.models.user import User
from app.services.file_processing.import_service import ImportService


UPLOAD_DIR = Path(settings.STORAGE_ROOT)


router = APIRouter(prefix='/user', tags=['User'])


@router.get('/', response_class=HTMLResponse)
async def user_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return templates.TemplateResponse(
        '/user/dashboard.html',
        {
            'request': request,
            'user': user,
        }
    )


@router.get('/upload', response_class=HTMLResponse)
async def get_upload_page(
    request: Request,
    user: User = Depends(get_current_user)
):
    return templates.TemplateResponse(
        '/user/competitors/upload.html',
        {
            'request': request,
            'user': user
        }
    )


@router.post('/upload', response_class=HTMLResponse)
async def upload_file(
    request: Request,
    file: UploadFile = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    file_id = uuid.uuid4()
    dir_path = UPLOAD_DIR / f"user_{user.id}"
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

    file_path = dir_path / f"{file_id}.xlsx"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # async with AsyncSessionLocal() as session:
    #     service = ImportService(session)
    #     import_id = await service.process_file(file_path, file.filename)
    service = ImportService(db)
    import_id = await service.process_file(file_path, file.filename)

    # return templates.TemplateResponse(
    #     "result.html",
    #     {
    #         "request": request,
    #         "import_id": import_id
    #     }
    # )
    return templates.TemplateResponse(
        '/user/competitors/result.html',
        {
            'request': request,
            'user': user,
            'import_id': import_id
        }
    )

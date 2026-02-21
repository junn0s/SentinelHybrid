from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from src.api.app_runtime import ApiRuntime
from src.api.routes.deps import get_runtime

router = APIRouter()


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/admin")


@router.get("/admin", include_in_schema=False)
def admin_page(runtime: ApiRuntime = Depends(get_runtime)) -> FileResponse:
    page = runtime.admin_dir / "index.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="Admin UI is not available.")
    return FileResponse(page)

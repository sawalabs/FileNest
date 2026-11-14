from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response

from backend.app.api.deps import get_filesystem_service
from backend.app.schemas.filesystem import (
    DirectoryListingResponse,
    FileItemMetadata,
    FolderSummaryResponse,
    GlobalSearchResponse,
)
from backend.app.services.filesystem import FilesystemService
from backend.app.services.managed_folder import ManagedFolderException

router = APIRouter()

MAX_SAFE_IMAGE_PIXELS = 50_000_000  # 50 MP limit against image decompression bomb


@router.get(
    "/browse",
    response_model=DirectoryListingResponse,
    summary="Browse directory entries within a Managed Folder",
)
def browse_directory(
    folder_id: str = Query(description="ID of the Managed Folder"),
    relative_path: str = Query(default="", description="Relative path within the Managed Folder"),
    include_hidden: bool = Query(default=False, description="Whether to include hidden files"),
    sort_by: str = Query(default="name", pattern="^(name|size|modified)$", description="Sort field: name, size, or modified"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$", description="Sort order: asc or desc"),
    service: FilesystemService = Depends(get_filesystem_service),
) -> DirectoryListingResponse:
    try:
        return service.list_directory(
            managed_folder_id=folder_id,
            relative_path=relative_path,
            include_hidden=include_hidden,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ManagedFolderException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/search",
    response_model=GlobalSearchResponse,
    summary="Search files and folders across registered Managed Folders",
)
def search_files(
    q: str = Query(min_length=1, max_length=255, description="Search query for file or folder names"),
    folder_id: Optional[str] = Query(default=None, description="Optional Managed Folder ID filter"),
    limit: int = Query(default=25, ge=1, le=100, description="Maximum search hits to return"),
    service: FilesystemService = Depends(get_filesystem_service),
) -> GlobalSearchResponse:
    try:
        return service.search_files(
            query=q,
            managed_folder_id=folder_id,
            limit=limit,
        )
    except ManagedFolderException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/metadata",
    response_model=FileItemMetadata,
    summary="Get metadata for a file or directory",
)
def get_metadata(
    folder_id: str = Query(description="ID of the Managed Folder"),
    relative_path: str = Query(description="Relative path to the file or directory"),
    service: FilesystemService = Depends(get_filesystem_service),
) -> FileItemMetadata:
    try:
        return service.get_item_metadata(
            managed_folder_id=folder_id,
            relative_path=relative_path,
        )
    except ManagedFolderException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/summary",
    response_model=FolderSummaryResponse,
    summary="Calculate recursive size and category distribution for a folder",
)
def get_folder_summary(
    folder_id: str = Query(description="ID of the Managed Folder"),
    relative_path: str = Query(default="", description="Relative path within the Managed Folder"),
    service: FilesystemService = Depends(get_filesystem_service),
) -> FolderSummaryResponse:
    try:
        return service.calculate_folder_summary(
            managed_folder_id=folder_id,
            relative_path=relative_path,
        )
    except ManagedFolderException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/reconcile",
    summary="Reconcile database records against live filesystem without modifying user files",
)
def reconcile_filesystem(
    folder_id: str = Query(description="ID of the Managed Folder to reconcile"),
    service: FilesystemService = Depends(get_filesystem_service),
) -> Dict[str, Any]:
    try:
        return service.reconcile_managed_folder(folder_id)
    except ManagedFolderException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/preview",
    summary="Securely stream image or binary preview for an in-scope file",
)
def get_file_preview(
    folder_id: str = Query(description="ID of the Managed Folder"),
    relative_path: str = Query(description="Relative path to file within the Managed Folder"),
    thumbnail: bool = Query(default=False, description="Whether to generate a downscaled thumbnail if image"),
    service: FilesystemService = Depends(get_filesystem_service),
):
    try:
        target, mime_type, _ = service.get_file_preview_stream(
            managed_folder_id=folder_id,
            relative_path=relative_path,
            thumbnail=thumbnail,
        )

        # SEC-10: Protect against image decompression bomb (pixel flood DoS)
        if mime_type.startswith("image/") and mime_type != "image/svg+xml":
            import warnings
            from PIL import Image

            prev_max = Image.MAX_IMAGE_PIXELS
            Image.MAX_IMAGE_PIXELS = MAX_SAFE_IMAGE_PIXELS
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(target) as img:
                        w, h = img.size
                        if w * h > MAX_SAFE_IMAGE_PIXELS:
                            raise HTTPException(
                                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail=f"Image dimensions ({w}x{h}) exceed safe pixel limit ({MAX_SAFE_IMAGE_PIXELS} pixels).",
                            )
                        if thumbnail:
                            import io

                            img.thumbnail((400, 400))
                            buf = io.BytesIO()
                            fmt = "PNG" if img.mode in ("RGBA", "P") else "JPEG"
                            img.save(buf, format=fmt, quality=85)
                            return Response(
                                content=buf.getvalue(),
                                media_type="image/png" if fmt == "PNG" else "image/jpeg",
                                headers={
                                    "Cache-Control": "private, max-age=3600",
                                    "X-Content-Type-Options": "nosniff",
                                },
                            )
            except (Image.DecompressionBombError, Image.DecompressionBombWarning):
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Image rejected: resolution exceeds safe decompression limit (Pixel Flood protection).",
                )
            except HTTPException:
                raise
            except Exception:
                pass
            finally:
                Image.MAX_IMAGE_PIXELS = prev_max

        headers = {
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        }
        if mime_type == "image/svg+xml":
            headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"

        return FileResponse(
            path=str(target),
            media_type=mime_type,
            headers=headers,
        )
    except ManagedFolderException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/preview/text",
    summary="Securely retrieve a bounded text/code snippet preview for an in-scope file",
)
def get_text_preview(
    folder_id: str = Query(description="ID of the Managed Folder"),
    relative_path: str = Query(description="Relative path to file within the Managed Folder"),
    max_bytes: int = Query(default=65536, ge=512, le=262144, description="Max bytes to preview (up to 256KB)"),
    service: FilesystemService = Depends(get_filesystem_service),
) -> Dict[str, Any]:
    try:
        return service.get_file_text_preview(
            managed_folder_id=folder_id,
            relative_path=relative_path,
            max_bytes=max_bytes,
        )
    except ManagedFolderException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

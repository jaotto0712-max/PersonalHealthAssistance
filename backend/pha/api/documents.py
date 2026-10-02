from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from pha.rag.parsers import ParseError
from pha.rag.registry import DocumentRecord
from pha.rag.service import DocumentService, FileTooLarge, UnsupportedFileType

router = APIRouter(prefix="/documents", tags=["documents"])

# multipart framing overhead allowed on top of the file-size limit for the early size check
MULTIPART_OVERHEAD = 64 * 1024


class DocumentOut(BaseModel):
    id: str
    filename: str
    size_bytes: int
    pages: int
    chunks: int
    status: Literal["indexed", "needs_ocr"]
    uploaded_at: datetime

    @classmethod
    def of(cls, record: DocumentRecord) -> "DocumentOut":
        return cls.model_validate(record.model_dump())


def get_documents(request: Request) -> DocumentService:
    service: DocumentService | None = request.app.state.documents
    if service is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=request.app.state.documents_error or "Document search is unavailable.",
        )
    return service


Documents = Annotated[DocumentService, Depends(get_documents)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Identical file already uploaded; existing record returned"},
        413: {"description": "File too large"},
        415: {"description": "Unsupported file type"},
        422: {"description": "File could not be read"},
    },
)
async def upload_document(
    request: Request,
    response: Response,
    file: UploadFile,
    service: Documents,
) -> DocumentOut:
    declared = request.headers.get("content-length", "")
    limit = service.max_upload_bytes + MULTIPART_OVERHEAD
    if declared.isdigit() and int(declared) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=_too_large(service))
    data = await file.read(service.max_upload_bytes + 1)
    try:
        result = await run_in_threadpool(
            service.ingest, file.filename or "", file.content_type, data
        )
    except UnsupportedFileType as e:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(e)) from e
    except FileTooLarge as e:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(e)) from e
    except ParseError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return DocumentOut.of(result.record)


@router.get("")
def list_documents(service: Documents) -> list[DocumentOut]:
    return [DocumentOut.of(r) for r in service.list()]


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: str, service: Documents) -> None:
    if not service.delete(doc_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found.")


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_documents(service: Documents) -> None:
    service.clear()


def _too_large(service: DocumentService) -> str:
    return f"File is larger than the {service.max_upload_bytes // (1024 * 1024)} MB limit."

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..auth.deps import get_admin_user
from ..core.database import get_driver
from ..db.models import User
from ..services.dataset_eval_service import export_task_csv, get_task, start_dataset_eval
from ..services.objective_doc_eval_service import (
    export_objective_task_csv_async,
    get_objective_task_record,
    start_objective_doc_eval,
)
from ..services.retrieval_harness_service import (
    export_retrieval_task_csv,
    get_retrieval_task,
    start_retrieval_harness,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/eval", tags=["admin"])


@router.post("/dataset")
async def create_eval_task(
    file: UploadFile = File(...),
    strategy: str = Form("parallel"),
    top_k: int = Form(5),
    driver=Depends(get_driver),
    current_user: User = Depends(get_admin_user),
):
    data = await file.read()
    try:
        return await start_dataset_eval(
            filename=file.filename or "dataset.xlsx",
            data=data,
            strategy=strategy,
            top_k=top_k,
            driver=driver,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/dataset/{task_id}")
async def eval_task_detail(
    task_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        return get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="评测任务不存在") from exc


@router.get("/dataset/{task_id}/csv")
async def eval_task_csv(
    task_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        text = export_task_csv(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="评测任务不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        iter([text]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="dataset_eval_{task_id}.csv"'},
    )


@router.post("/objective-doc")
async def create_objective_doc_task(
    file: UploadFile = File(...),
    strategy: str = Form("parallel"),
    top_k: int = Form(5),
    driver=Depends(get_driver),
    current_user: User = Depends(get_admin_user),
):
    data = await file.read()
    try:
        return await start_objective_doc_eval(
            filename=file.filename or "objective.docx",
            data=data,
            strategy=strategy,
            top_k=top_k,
            driver=driver,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/objective-doc/{task_id}")
async def objective_doc_task_detail(
    task_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        return await get_objective_task_record(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="客观题任务不存在") from exc


@router.get("/objective-doc/{task_id}/csv")
async def objective_doc_task_csv(
    task_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        text = await export_objective_task_csv_async(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="客观题任务不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        iter([text]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="objective_doc_eval_{task_id}.csv"'},
    )


@router.post("/retrieval")
async def create_retrieval_harness_task(
    file: UploadFile = File(...),
    strategy: str = Form("parallel"),
    top_k: int = Form(5),
    driver=Depends(get_driver),
    current_user: User = Depends(get_admin_user),
):
    del current_user
    data = await file.read()
    try:
        return await start_retrieval_harness(
            filename=file.filename or "retrieval_cases.jsonl",
            data=data,
            strategy=strategy,
            top_k=top_k,
            driver=driver,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/retrieval/{task_id}")
async def retrieval_harness_task_detail(
    task_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        return get_retrieval_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="检索评测任务不存在") from exc


@router.get("/retrieval/{task_id}/csv")
async def retrieval_harness_task_csv(
    task_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        text = export_retrieval_task_csv(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="检索评测任务不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        iter([text]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="retrieval_harness_{task_id}.csv"'},
    )

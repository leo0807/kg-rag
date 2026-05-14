import traceback
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from ...auth.deps import get_admin_user
from ...core.database import get_driver
from ...db.models import User
from ...services.evaluation.dataset_eval_service import export_task_csv, get_task, start_dataset_eval
from ...services.evaluation.objective_doc_eval_service import (
    export_objective_task_csv_async,
    get_objective_task_record,
    list_objective_task_records,
    start_objective_doc_eval,
)
from ...services.evaluation.retrieval_harness_service import (
    export_retrieval_task_csv,
    get_retrieval_task,
    start_retrieval_harness,
)
from ...services.evaluation.faithfulness_service import (
    export_faithfulness_csv,
    get_faithfulness_task,
    start_faithfulness_eval,
)
from ...services.evaluation.ab_test_service import (
    export_ab_csv,
    get_ab_task,
    start_ab_test,
)

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
    source_doc_id: str = Form(""),
    doc_id: str = Form(""),
    driver=Depends(get_driver),
    current_user: User = Depends(get_admin_user),
):
    print("\n>>>>> [EVAL_ROUTE_HIT] 评测请求到达 <<<<<", flush=True)
    print(
        f"  user={getattr(current_user, 'username', None) or getattr(current_user, 'email', None) or getattr(current_user, 'id', None)} filename={file.filename or ''} strategy={strategy} top_k={top_k} source_doc_id={source_doc_id or doc_id or '-'}",
        flush=True,
    )
    data = await file.read()
    try:
        print(f"[EVAL_STEP1] file read ok bytes={len(data)} filename={file.filename or ''}", flush=True)
        print("[EVAL_STEP2] starting objective doc eval service", flush=True)
        return await start_objective_doc_eval(
            filename=file.filename or "objective.docx",
            data=data,
            strategy=strategy,
            top_k=top_k,
            driver=driver,
            source_doc_id=source_doc_id.strip(),
            doc_id=doc_id.strip(),
        )
    except ValueError as exc:
        print(f"[EVAL_ERROR] objective-doc failed: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
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
@router.get("/objective-doc")
async def objective_doc_task_list(
    limit: int = 20,
    _: User = Depends(get_admin_user),
):
    return await list_objective_task_records(limit=limit)
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
# ── Faithfulness ──────────────────────────────────────────────────────────────

@router.post("/faithfulness")
async def create_faithfulness_task(
    file: UploadFile = File(...),
    _: User = Depends(get_admin_user),
):
    data = await file.read()
    try:
        return await start_faithfulness_eval(
            filename=file.filename or "faithfulness.jsonl",
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
@router.get("/faithfulness/{task_id}")
async def faithfulness_task_detail(
    task_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        return get_faithfulness_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="忠实度任务不存在") from exc
@router.get("/faithfulness/{task_id}/csv")
async def faithfulness_task_csv(
    task_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        text = export_faithfulness_csv(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="忠实度任务不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        iter([text]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="faithfulness_{task_id}.csv"'},
    )
# ── A/B Test ──────────────────────────────────────────────────────────────────

@router.post("/ab-test")
async def create_ab_test_task(
    file: UploadFile = File(...),
    strategies: str = Form("parallel,graph_augmented"),
    top_k: int = Form(5),
    driver=Depends(get_driver),
    _: User = Depends(get_admin_user),
):
    data = await file.read()
    strategy_list = [s.strip() for s in strategies.split(",") if s.strip()]
    try:
        return await start_ab_test(
            filename=file.filename or "ab_cases.jsonl",
            data=data,
            strategies=strategy_list,
            top_k=top_k,
            driver=driver,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ab-test/{task_id}")
async def ab_test_task_detail(
    task_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        return get_ab_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="A/B 测试任务不存在") from exc


@router.get("/ab-test/{task_id}/csv")
async def ab_test_task_csv(
    task_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        text = export_ab_csv(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="A/B 测试任务不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        iter([text]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="ab_test_{task_id}.csv"'},
    )

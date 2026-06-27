#!/usr/bin/env python3
"""
Export bge-reranker-v2-m3 to TensorRT Engine for NVIDIA T4/A10.

Expected latency reduction: 80ms → ~15ms per rerank batch (batch=32, seq=256)

Steps:
  1. Export HuggingFace model → ONNX (via optimum)
  2. Convert ONNX → TensorRT .engine (via trtexec or tensorrt Python API)
  3. Benchmark ONNX vs TensorRT latency

Usage:
    pip install optimum[exporters] tensorrt onnxruntime-gpu
    python scripts/export_tensorrt_reranker.py \
        --model-name BAAI/bge-reranker-v2-m3 \
        --output-dir models/bge-reranker-trt \
        [--fp16] [--benchmark]

Prerequisites:
    - NVIDIA GPU with CUDA 11.8+ and TensorRT 8.6+
    - ONNX Runtime GPU build: pip install onnxruntime-gpu
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def export_onnx(model_name: str, output_dir: Path) -> Path:
    """Export reranker to ONNX using optimum."""
    try:
        from optimum.exporters.onnx import main_export
    except ImportError:
        raise RuntimeError("pip install optimum[exporters]")

    onnx_path = output_dir / "reranker_onnx"
    onnx_path.mkdir(parents=True, exist_ok=True)
    log.info("Exporting %s to ONNX ...", model_name)
    main_export(
        model_name_or_path=model_name,
        output=onnx_path,
        task="text-classification",
        framework="pt",
        device="cpu",
        opset=17,
    )
    model_file = onnx_path / "model.onnx"
    log.info("ONNX saved to %s", model_file)
    return model_file


def build_tensorrt_engine(onnx_path: Path, engine_path: Path, fp16: bool) -> None:
    """Convert ONNX to TensorRT .engine using the Python API."""
    try:
        import tensorrt as trt
    except ImportError:
        raise RuntimeError("pip install tensorrt")

    TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(TRT_LOGGER)
    network = builder.create_network(
        1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    )
    parser = trt.OnnxParser(network, TRT_LOGGER)

    log.info("Parsing ONNX model ...")
    with open(onnx_path, "rb") as f:
        if not parser.parse(f.read()):
            for i in range(parser.num_errors):
                log.error("TRT parse error: %s", parser.get_error(i))
            raise RuntimeError("ONNX parse failed")

    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 4 << 30)  # 4 GB

    if fp16 and builder.platform_has_fast_fp16:
        config.set_flag(trt.BuilderFlag.FP16)
        log.info("FP16 precision enabled")

    # Dynamic shape profile: batch 1–64, seq 1–512
    profile = builder.create_optimization_profile()
    for input_name in ["input_ids", "attention_mask", "token_type_ids"]:
        profile.set_shape(input_name,
                          min=(1, 1), opt=(16, 256), max=(64, 512))
    config.add_optimization_profile(profile)

    log.info("Building TensorRT engine (this may take several minutes) ...")
    serialized_engine = builder.build_serialized_network(network, config)
    if serialized_engine is None:
        raise RuntimeError("TensorRT engine build failed")

    engine_path.parent.mkdir(parents=True, exist_ok=True)
    with open(engine_path, "wb") as f:
        f.write(serialized_engine)
    log.info("Engine saved to %s (%d MB)", engine_path,
             os.path.getsize(engine_path) >> 20)


def benchmark(onnx_path: Path, engine_path: Path,
              batch: int = 32, seq: int = 256, n_runs: int = 50) -> dict:
    """Compare ONNX Runtime vs TensorRT latency."""
    results: dict = {}

    # ── ONNX Runtime (GPU) ───────────────────────────────────────────────────
    try:
        import onnxruntime as ort
        import numpy as np

        sess = ort.InferenceSession(
            str(onnx_path),
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        dummy = {
            "input_ids":      np.ones((batch, seq), dtype=np.int64),
            "attention_mask": np.ones((batch, seq), dtype=np.int64),
            "token_type_ids": np.zeros((batch, seq), dtype=np.int64),
        }
        for _ in range(5):  # warm-up
            sess.run(None, dummy)

        t0 = time.perf_counter()
        for _ in range(n_runs):
            sess.run(None, dummy)
        ort_ms = (time.perf_counter() - t0) / n_runs * 1000
        results["onnx_ms"] = round(ort_ms, 2)
        log.info("ONNX Runtime (GPU): %.1f ms/batch", ort_ms)
    except Exception as exc:
        log.warning("ONNX benchmark skipped: %s", exc)

    # ── TensorRT ─────────────────────────────────────────────────────────────
    try:
        import tensorrt as trt
        import numpy as np
        import pycuda.autoinit  # noqa: F401
        import pycuda.driver as cuda

        TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
        runtime = trt.Runtime(TRT_LOGGER)
        with open(engine_path, "rb") as f:
            engine = runtime.deserialize_cuda_engine(f.read())
        context = engine.create_execution_context()
        context.set_input_shape("input_ids", (batch, seq))

        h_in  = np.ones((batch, seq), dtype=np.int64)
        h_out = np.empty((batch, 1), dtype=np.float32)
        d_in  = cuda.mem_alloc(h_in.nbytes)
        d_out = cuda.mem_alloc(h_out.nbytes)

        for _ in range(5):
            cuda.memcpy_htod(d_in, h_in)
            context.execute_v2([int(d_in), int(d_out)])
        t0 = time.perf_counter()
        for _ in range(n_runs):
            cuda.memcpy_htod(d_in, h_in)
            context.execute_v2([int(d_in), int(d_out)])
        trt_ms = (time.perf_counter() - t0) / n_runs * 1000
        results["trt_ms"] = round(trt_ms, 2)
        log.info("TensorRT: %.1f ms/batch (speedup %.1f×)",
                 trt_ms, results.get("onnx_ms", trt_ms) / trt_ms)
    except Exception as exc:
        log.warning("TensorRT benchmark skipped: %s", exc)

    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", default="BAAI/bge-reranker-v2-m3")
    parser.add_argument("--output-dir", default="models/bge-reranker-trt")
    parser.add_argument("--fp16", action="store_true", default=True,
                        help="Use FP16 (default True on T4/A10)")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--seq-len", type=int, default=256)
    args = parser.parse_args()

    out = Path(args.output_dir)
    engine_path = out / "reranker.engine"

    onnx_path = export_onnx(args.model_name, out)
    build_tensorrt_engine(onnx_path, engine_path, fp16=args.fp16)

    if args.benchmark:
        results = benchmark(onnx_path, engine_path,
                            batch=args.batch, seq=args.seq_len)
        print("\n── Benchmark results ──────────────────")
        for k, v in results.items():
            print(f"  {k}: {v} ms")
        if "onnx_ms" in results and "trt_ms" in results:
            speedup = results["onnx_ms"] / results["trt_ms"]
            print(f"  speedup: {speedup:.1f}×")


if __name__ == "__main__":
    main()

"""Benchmark: Gemma 4 E4B (official google-deepmind/gemma JAX library) on winjax.

Measures steady-state batch-1 greedy decode latency on the GPU after warmup.

Two independent measurements:
  A) Differencing: whole sample() calls with max_new_tokens=64 vs 320; the
     decode loop is a jax.lax.while_loop on device, so the difference divided
     by 256 is the pure per-token decode cost (prefill/tokenize overheads
     cancel out).
  B) Streaming: sample(stream=True) drives the jitted single-step function
     from Python, one token per iteration -> direct per-token wall times.

End/stop tokens are forbidden via logit masking so generation never stops
early and token counts are exact.

Checkpoint: official Orbax checkpoint from gs://gemma-data (downloaded to
models/gemma4-e4b-it), stored in float32; restored directly as bfloat16 on
the GPU by overriding the restore target dtype.
"""

import statistics
import subprocess
import time

t_proc0 = time.perf_counter()

import jax
import jax.numpy as jnp

CKPT = os.environ.get("GEMMA_CKPT_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "gemma4-e4b-it"))
TOK = os.environ.get("GEMMA_TOKENIZER", os.path.join(os.path.dirname(CKPT), "tokenizer_gemma4.model"))

PROMPT = (
    "<start_of_turn>user\n"
    "Write a detailed essay about the history of computing, starting with "
    "Charles Babbage.<end_of_turn>\n"
    "<start_of_turn>model\n"
)

WARMUP_TOKENS = 16
SHORT = 64
LONG = 320
REPS = 3
STREAM_TOTAL = 288
STREAM_SKIP = 16


def gb(n):
    return n / 2**30


def mem_report(tag):
    dev = jax.devices()[0]
    s = dev.memory_stats()
    print(
        f"[mem] {tag}: in_use={gb(s['bytes_in_use']):.2f} GiB, "
        f"peak={gb(s['peak_bytes_in_use']):.2f} GiB, "
        f"limit={gb(s.get('bytes_limit', 0)):.2f} GiB",
        flush=True,
    )
    return s


def nvidia_smi():
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(f"[nvidia-smi] {out.stdout.strip()}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[nvidia-smi] unavailable: {e}", flush=True)


def main():
    print(f"jax {jax.__version__}, devices: {jax.devices()}", flush=True)
    assert jax.devices()[0].platform == "gpu", "CUDA device not found"

    from gemma import gm  # noqa: PLC0415 (import after jax init print)
    from gemma.gm.ckpts import _checkpoint as gmc  # noqa: PLC0415

    print(f"imports done at t={time.perf_counter()-t_proc0:.1f} s", flush=True)

    # ---- Cap orbax restore concurrency. The default (96 GB in flight) makes
    # tensorstore exhaust Windows commit memory while reading the 29 GB f32
    # checkpoint (glog FATAL in memory_region.cc: "Failed to allocate memory").
    import orbax.checkpoint as ocp  # noqa: PLC0415

    _OrigStandardCheckpointer = ocp.StandardCheckpointer

    class _LowConcurrencyCheckpointer(_OrigStandardCheckpointer):

        def __init__(self, **kw):
            kw.setdefault("restore_concurrent_gb", 8)
            super().__init__(**kw)

    ocp.StandardCheckpointer = _LowConcurrencyCheckpointer

    # ---- Restore-dtype override: checkpoint stores float32; restore as bf16.
    kd = gmc.kd

    def _bf16_shape_dtype_struct(tree):
        def leaf(x):
            dt = x.dtype
            if jnp.issubdtype(dt, jnp.floating):
                dt = jnp.bfloat16
            return jax.ShapeDtypeStruct(
                dtype=dt, shape=x.shape, sharding=kd.sharding.REPLICATED
            )

        return jax.tree.map(leaf, tree)

    gmc._as_shape_dtype_struct = _bf16_shape_dtype_struct

    tokenizer = gm.text.Gemma4Tokenizer(path=TOK)
    model = gm.nn.Gemma4_E4B()  # text_only=True by default

    mem_report("before param load")
    t0 = time.perf_counter()
    params = gm.ckpts.load_params(CKPT, text_only=True)
    n_params = sum(x.size for x in jax.tree.leaves(params))
    p_bytes = sum(x.size * x.dtype.itemsize for x in jax.tree.leaves(params))
    t_load = time.perf_counter() - t0
    print(
        f"params loaded in {t_load:.1f} s: {n_params/1e9:.3f} B params, "
        f"{gb(p_bytes):.2f} GiB on device, "
        f"dtypes={{ {set(str(x.dtype) for x in jax.tree.leaves(params))} }}",
        flush=True,
    )
    mem_report("after param load")

    st = tokenizer.special_tokens
    sampler = gm.text.Sampler(
        model=model,
        params=params,
        tokenizer=tokenizer,
        cache_length=1024,
        max_out_length=512,
        forbidden_tokens=(
            int(st.EOS),
            int(st.END_OF_TURN),
            int(st.BEGIN_OF_TOOL_RESPONSE),
        ),
    )

    n_prompt = len(tokenizer.encode(PROMPT))
    print(f"prompt tokens: {n_prompt}", flush=True)

    # ---- Warmup (compilation + autotuning) ----
    t0 = time.perf_counter()
    out = sampler.sample(PROMPT, max_new_tokens=WARMUP_TOKENS)
    t_warm = time.perf_counter() - t0
    print(f"warmup sample ({WARMUP_TOKENS} tok) incl. compile: {t_warm:.1f} s")
    print(f"warmup output: {out[:120]!r}", flush=True)

    t0 = time.perf_counter()
    sampler.sample(PROMPT, max_new_tokens=WARMUP_TOKENS)
    t_warm2 = time.perf_counter() - t0
    print(f"second warmup sample ({WARMUP_TOKENS} tok), no compile: "
          f"{t_warm2*1e3:.0f} ms", flush=True)
    mem_report("after warmup")

    # ---- Measurement A: differencing 64 vs 320 tokens ----
    diffs = []
    for rep in range(REPS):
        t0 = time.perf_counter()
        sampler.sample(PROMPT, max_new_tokens=SHORT)
        t_short = time.perf_counter() - t0
        t0 = time.perf_counter()
        long_text = sampler.sample(PROMPT, max_new_tokens=LONG)
        t_long = time.perf_counter() - t0
        per_tok = (t_long - t_short) / (LONG - SHORT) * 1e3
        diffs.append(per_tok)
        print(
            f"rep {rep}: {SHORT} tok = {t_short:.3f} s, {LONG} tok = "
            f"{t_long:.3f} s -> {per_tok:.2f} ms/token",
            flush=True,
        )
    print(f"[A] differencing per-token: mean={statistics.mean(diffs):.2f} ms, "
          f"median={statistics.median(diffs):.2f} ms", flush=True)
    print(f"[A] sample of long output: {long_text[:300]!r}", flush=True)

    # ---- Measurement B: streaming, direct per-token times ----
    stream_times = []
    last = time.perf_counter()
    n_stream = 0
    for _ in sampler.sample(PROMPT, max_new_tokens=STREAM_TOTAL, stream=True):
        now = time.perf_counter()
        stream_times.append(now - last)
        last = now
        n_stream += 1
    steady = [t * 1e3 for t in stream_times[STREAM_SKIP:]]
    med = statistics.median(steady)
    mean = statistics.mean(steady)
    print(
        f"[B] streaming: {n_stream} tokens generated "
        f"(first step incl. compile = {stream_times[0]:.2f} s), "
        f"steady-state over last {len(steady)}:",
        flush=True,
    )
    print(
        f"[B] per-token: median={med:.2f} ms, mean={mean:.2f} ms, "
        f"p5={sorted(steady)[int(0.05*len(steady))]:.2f}, "
        f"p95={sorted(steady)[int(0.95*len(steady))]:.2f}, "
        f"tokens/s (median)={1e3/med:.1f}",
        flush=True,
    )

    mem_report("after benchmark (peak includes load)")
    nvidia_smi()

    print("\n===== SUMMARY =====")
    print("model: Gemma 4 E4B instruction-tuned (official DeepMind JAX impl)")
    print(f"params on GPU: {n_params/1e9:.3f} B ({gb(p_bytes):.2f} GiB bf16)")
    print(f"warmup incl. compile: {t_warm:.1f} s")
    print(
        f"decode per-token (A, while_loop differencing): "
        f"median={statistics.median(diffs):.2f} ms "
        f"({1e3/statistics.median(diffs):.1f} tok/s)"
    )
    print(
        f"decode per-token (B, streamed steps): median={med:.2f} ms, "
        f"mean={mean:.2f} ms ({1e3/med:.1f} tok/s median)"
    )


if __name__ == "__main__":
    main()

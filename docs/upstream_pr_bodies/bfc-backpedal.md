## Symptom

When a sub-allocator persistently fails a small allocation, `BFCAllocator::Extend` spins forever in its backpedal loop, emitting an unbounded stream of "could not allocate" warnings (observed: 5 GB of log within minutes, tests turned into multi-hour timeouts instead of clean allocation errors).

## Root cause

The backpedal loop in `BFCAllocator::Extend` (`xla/tsl/framework/bfc_allocator.cc`) shrinks the attempt by 10% per iteration, but re-rounds the result with `RoundedBytes`, which rounds *up* to a multiple of `kMinAllocationSize` (256 bytes):

```cpp
while (mem_addr == nullptr) {
  bytes = RoundedBytes(bytes * kBackpedalFactor);
  if (bytes < rounded_bytes) return false;
  mem_addr = sub_allocator_->Alloc(alignment, bytes, &bytes_received);
}
```

For `bytes < 10 * kMinAllocationSize` (i.e. up to 2304 bytes), `RoundedBytes(0.9 * bytes)` rounds back up to the same value, so the attempt size never decreases and the loop never terminates while the sub-allocator keeps failing.

## Fix

Force strict progress: if the re-rounded backpedal size did not decrease, step down by one `kMinAllocationSize` instead. The loop then always reaches `bytes < rounded_bytes` and returns a clean allocation failure.

The bug is platform-independent (any persistently failing sub-allocator triggers it). It was found while porting XLA to native Windows, where pinned-host `cuMemHostAlloc` can keep failing under WDDM commit pressure after the device pool has taken the GPU budget.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

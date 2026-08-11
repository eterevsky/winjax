## Symptom

A collective-permute with an empty source-target-pairs list — jax emits one for the gradient of `ppermute` on a single device — fails with `UNIMPLEMENTED` on builds without collectives support, because the emitted thunk tries to acquire a communicator that no data transfer needs.

## Root cause

`CollectivePermuteThunk::IsDegenerate` treats the empty-pairs case as *not* degenerate (the pair list does not cover all participants), so `ThunkEmitter::EmitCollective` produces a full `CollectivePermuteThunk`. At run time the collective runtime implements "no source for this rank" by zeroing the output (see `RunCollectivePermute`), so the communicator acquisition is pure overhead — and a hard failure on builds compiled without collectives (e.g. native Windows, which has no NCCL).

## Fix

In `ThunkEmitter::EmitCollective`, when the instruction is a collective-permute with no source-target pairs, emit a `MemzeroThunk` per output buffer instead of the collective thunk. This is semantically identical (every participant's output is zeroed), cheaper everywhere, and keeps such programs working on collectives-less builds. The copy-based degenerate path is intentionally not reused: a degenerate permute copies input to output, whereas the empty permute must zero the output.

Found while porting XLA to native Windows; fixes jax's `pmap_test::testCollectivePermuteGrad` there.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

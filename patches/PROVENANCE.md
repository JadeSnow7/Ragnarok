# Todo persistence patch provenance

- Prepared by the coding assistant on 2026-10-02 as an **agent-assisted, pre-generated patch** for this bounded proof of concept. The prototype does not call an embedded model or independently generate a new fix at runtime.
- Source fixture: `fixture/store.mjs`. Baseline deliberately omits the persistence write in `toggle(id)`; add, remove, and restore already work.
- Fix: `todo-persistence.patch` replaces the baseline explanatory comment with `persist()` immediately after changing `completed`.
- Patch scope: **only `fixture/store.mjs`**. No tests, UI, storage keys, dependencies, credentials, or network settings are changed.
- Tests are real Node built-in `node:test` assertions. Reload is modeled by constructing a fresh store over the same Web Storage mock. This is store-level verification, not an automated browser test.
- Verified here using Node `v24.19.0`: unchanged baseline **9 pass / 1 fail**; isolated patched copy **10 pass / 0 fail**.
- Expected failing test (exact): `checkbox state survives reload after toggling`.
- Browser reproduction: open the served fixture, add a task, check it, and immediately use **Reload fixture**. Do not add or remove another task before reloading; those unrelated actions already write the full store.

## Exact commands

Run from the `gosim-handoff` project root. No install is required.

The unchanged baseline command must exit **1**:

```sh
node --test --test-reporter=tap fixture/store.test.mjs
```

The following isolated-copy command must exit **0**. The original fixture and tests remain unchanged:

```sh
(
  set -eu
  verify_dir=$(mktemp -d patches/.verify-XXXXXX)
  trap 'rm -rf "$verify_dir"' EXIT
  cp -R fixture "$verify_dir/fixture"
  patch_path="$PWD/patches/todo-persistence.patch"
  git -C "$verify_dir" apply --check "$patch_path"
  git -C "$verify_dir" apply "$patch_path"
  cmp fixture/store.test.mjs "$verify_dir/fixture/store.test.mjs"
  node --test --test-reporter=tap "$verify_dir/fixture/store.test.mjs"
)
```

## Content fingerprints

SHA-256, before applying the patch:

```text
5f5fd17fe4f7b05752b8fbcf974e176dcd268101161a20135ac4564ebfc39d76  fixture/store.mjs
19281d5f7ccbeed81d5abe2a637bc567134ae02200161245ef6a71b49c034042  fixture/store.test.mjs
39b7c0a69542ce51c8751fb0c262a5ead5e04868ce762e1138bd8de03e8d6a4d  patches/todo-persistence.patch
```

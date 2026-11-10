# test_tenant_zero_holds_no_secret.py

## What it proves

This tenant's stack holds no secret value, from four facts that are files in
this checkout:

- `package.json` pins `@branchleft/ghost-platform-tenant` at `8.0.0`, the
  first release that takes no `secrets` argument and exposes no secret output.
- `config.ts` and `index.ts`, with their comments taken out, contain no
  `requireSecret`, `getSecret`, `pulumi.secret(`, `secrets:` argument,
  `secretsEnvFile` output or `ownerEmail`.
- No committed `Pulumi.<stack>.yaml` has a `secure:` entry or a key named like a
  credential. The decision is `assert-no-secure-stack-config.py`'s, loaded by
  path, so there is one definition of "holds a secret".

CI's `Committed-secret guard` job runs every `scripts/test_*.py`, so this runs
on every pull request.

## Control cases

An empty list only means something if the detector can return a hit. The last
class plants each shape in a string and requires it to be found, and requires a
comment that merely names one, and a URL's `//`, to be read correctly. The
stack-config half has its own controls in `test_assert_no_secure_stack_config.py`.

## What it does not prove

- Stack state. A state file is checked with
  `assert-no-secure-stack-config.py --state FILE`, run by hand on the output of
  `pulumi stack export` after the apply.
- That the host holds the right values. The host renders its own secrets file;
  nothing here reads one.

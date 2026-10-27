# blog — Ghost platform tenant stack

The infrastructure repo for one tenant of the branchLeft Ghost hosting
platform: stack `blog`, generated from
[`ghost-platform-tenant-template`](https://github.com/branchLeft/ghost-platform-tenant-template).

One Pulumi program (`index.ts`), one stack, one tenant. The reusable,
tenant-anonymous `GhostTenant` component lives in the public
[`ghost-platform`](https://github.com/branchLeft/ghost-platform) repo, published
as `@branchleft/ghost-platform-tenant`; this repo holds only this tenant's stack
invocation — its slug, hostname, UID, port and credentials.

**A hostname plus a slug is this tenant's identity.** Never carry either into a
public repo, an issue, or a pull-request description outside this repo.

## What this stack does, and does not

**It creates nothing.** Everything durable this tenant uses already exists: the
app host and `db1` are shared with other tenants, and this tenant's Object
Storage bucket is its own — created by an operator before this stack first
applied, because Hetzner mints S3 credentials only in its Cloud Console. What is
per-tenant here is *configuration*, and this stack is the versioned,
passphrase-wrapped record of it. `pulumi up` renders two things an operator places on the host by hand:

```bash
pulumi stack output composeFile                      # /opt/branchleft/blog/compose.yml
pulumi stack output --show-secrets secretsEnvFile    # /etc/branchleft/blog.env, 0600
```

Both are root-owned and operator-written. No automated path may write either:
between them they are the runtime-isolation posture, and a stack that quietly
loses one line of it still starts, still serves, and has dropped a boundary.

**The only thing CI puts on the host is an image reference.** The deploy job
pipes `imageRef` to `branchleft-deploy` over this repo's own slot key, which
writes `/etc/branchleft/blog.image.env` and restarts
`branchleft-compose@blog`. That key's `authorized_keys` entry carries
a forced command naming this stack, written by root — so it cannot address any
other tenant on that host, because there is no caller-supplied stack name
anywhere on the path.

## Day-to-day

- CI (`.github/workflows/infra-ci.yml`) type-checks every pull request, and on
  `main` applies the `blog` stack and then deploys its pinned image.
  Both jobs refuse to run while a template placeholder survives, and the deploy
  job's delete-guard preflight aborts any plan carrying a `delete` or `replace`
  step. Its other half does not currently fire — see the `uid` bullet below.
- Changes are pull requests against `Pulumi.blog.yaml` and
  `index.ts`. Secret config is encrypted with this repo's own passphrase — set
  it with `pulumi config set --secret` from a checkout, with
  `PULUMI_CONFIG_PASSPHRASE` exported locally, never by pasting plaintext into
  the file.
- **Changing the image** is a one-line change to `imageRef`, digest-pinned. A
  tag is refused at preview: a stack deployed by tag has no answer to "what is
  running", and a restart months later can silently change it.
- **Changing `uid` or `appHostPrivateIp` is refused at preview**, and both
  orphan live data rather than updating it: the container would start under a
  UID that cannot read its own `0700` content volume. The delete guard compares
  the component's registered identity — `uid`, `stackName`, `contentVolume`,
  `adaptersVolume`, `databaseName`, `appHostPrivateIp` — and refuses the plan if
  any of them moves. Treat them as fields to change only with a migration in
  front of them; CI will now stop you, but it stops you rather than migrating
  anything. Changing the **slug** is refused too, because Pulumi renders that as
  a delete and a create.

  This holds from component `3.0.0`. Below that the identity comparison matched
  no steps at all and a changed `uid` applied clean — reproduced, and fixed in
  [branchLeft/workspace#280](https://github.com/branchLeft/workspace/issues/280).
- **`edgeRequestBodyMaxSize`** has to reach this tenant's site block in the
  edge's site registry in `branchLeft/shared-infra`. It is derived from the same
  input as the container's `/tmp` ceiling so the two cannot disagree; setting it
  there by hand to a different number defeats that.
- This stack's `encryptionsalt` lives in the `PULUMI_ENCRYPTION_SALT`
  environment secret, not in the committed config. The deploy job appends it to
  the working copy for that job alone. To run `pulumi` locally, append your own
  held copy and do not commit it:
  `printf '\nencryptionsalt: %s\n' "$PULUMI_ENCRYPTION_SALT" >> Pulumi.blog.yaml`
- `scripts/assert-no-committed-pulumi-secrets.py` fails a commit, and CI's
  `Committed-secret guard` job fails a pull request, that puts a salt back.

Bootstrap record, the host-side steps and the teardown order:
`RUNBOOK-bootstrap.md`.

## Repo variables and environment secrets

CI reads two repository variables, `PULUMI_BACKEND_URL` (the full
`s3://…?endpoint=…&s3ForcePathStyle=true&region=…` state backend URL, not a
bucket name) and `APP_HOST_SSH_ADDRESS` (the app host's **public** address), and
keeps every credential as an environment secret, never a repository secret. A
repository secret is readable by any workflow run in the repo, including one
added on a branch; an environment secret is readable only by a job declaring
that environment.

The `production` environment holds `PULUMI_CONFIG_PASSPHRASE`,
`PULUMI_ENCRYPTION_SALT`, `HETZNER_S3_ACCESS_KEY_ID`,
`HETZNER_S3_SECRET_ACCESS_KEY` and `APP_HOST_DEPLOY_KEY`, and is read by the
deploy job alone.

**A second environment, `production-plan`, for the plan job.** The `plan` job
previews the stack on main before the deploy job waits for its approval, so
whoever approves can read what the apply would do. A preview needs the same four
secrets as the apply (`PULUMI_CONFIG_PASSPHRASE`, `PULUMI_ENCRYPTION_SALT` and
the two `HETZNER_S3_*` keys), and no job outside the gated one may read them
from `production`. So the same four secret names are also set, with the same
values, on `production-plan`. That environment carries no reviewer (it would stop
the job before the plan exists) and **must** have a deployment branch policy
naming `main` alone; the plan job's first step refuses to run otherwise. It
holds no `APP_HOST_DEPLOY_KEY`, and the job runs no `pulumi up`. It cannot run
on a pull request, because a branch must not read these secrets: a pull request
is checked by the type check, and the plan is made after the merge.

**A push that changes nothing skips the deploy job, and says so.** The plan job
publishes one value, `has_changes`, and the deploy job's `if:` skips it, and so
its approval, only when that is exactly `false`. It is `false` only when two
checks both find no change: the `plan-has-changes` action reads the Pulumi plan,
and `scripts/image-changed.py` compares `imageRef` with the one the last
successful run on main shipped. The second exists because the deploy job also
puts the image on the host over SSH, which a plan of nothing but unchanged
resources does not show. Anything either cannot establish asks for the approval
as before. The first line of the plan job's summary says which way it went and
why; `scripts/image-changed.md` has the rules.

Set them in this order. Until the branch policy names `main` alone, any branch
could read the four secrets, so the secrets come last.

| Step | What                                        | Where                         | Set by                                    |
| ---- | ------------------------------------------- | ----------------------------- | ----------------------------------------- |
| 1    | create the `production-plan` environment, with no reviewer | repo settings  | the owner                                 |
| 2    | deployment branch policy: `main` alone      | `production-plan` environment | the owner, in repo settings               |
| 3    | the four state and passphrase secrets above | `production-plan` env secrets | the owner, copying the `production` values |

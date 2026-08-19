# blog — Ghost platform tenant stack

The infrastructure stack for the branchLeft blog (`blog.branchleft.co.uk`),
tenant zero of the branchLeft Ghost hosting platform. It is published as a
worked example of what a live tenant stack looks like: one Pulumi program
(`index.ts`), one stack, one tenant.

The reusable, tenant-anonymous `GhostTenant` component lives in the public
[`ghost-platform`](https://github.com/branchLeft/ghost-platform) repo,
published as `@branchleft/ghost-platform-tenant`; this repo holds only this
tenant's stack invocation — its name, hostname and config. Each further tenant
is a separate repo generated from a private template, so nothing here is
shared mutable state.

**This repo declares no identity.** The deployer service account, its
Workload Identity pool and provider, its project roles, this tenant's Pulumi
state bucket and the KMS binding were created by the platform's provisioning
flow and live in that flow's state — a Pulumi program cannot create the
identity it runs as. What arrived here instead at provisioning time: four
stack config values (the database instance connection name, the tenant image
repository path, the media bucket URL, the deployer service account email),
three repo variables and one repo secret. On top of that, the deploy job
requires four owner-seeded repository secrets, and fails closed without any of
them: `BLOG_MAIL_SMTP_PASSWORD` and `BLOG_BULK_EMAIL_API_KEY`, injected into
the stack config at runtime, and the two under *Stack secrets* below.

## Day-to-day

- CI (`.github/workflows/infra-ci.yml`) type-checks every pull request and
  applies `main` to the `blog` stack. Both jobs refuse to run if a
  template placeholder survives, and the deploy job's delete-guard preflight
  aborts any plan that would destroy this tenant's resources.
- Changes are pull requests against `Pulumi.blog.yaml` and `index.ts`.
- The two mail credentials (`mailSmtpPassword`, `bulkEmailApiKey`) are **not**
  committed to `Pulumi.blog.yaml`. They are held as repository Actions secrets
  and encrypted into the stack config by the deploy job at runtime, so no live
  credential sits in this public tree. Any further secret value follows the
  same pattern.
- The mail and bulk-email config keys this stack consumes are the
  `blog-infra:mail*` and `blog-infra:bulkEmail*` values in `Pulumi.blog.yaml`;
  `GhostTenantMailArgs` and `GhostTenantBulkEmailArgs` in
  `@branchleft/ghost-platform-tenant` define what they become.
- The standards gate (`.github/workflows/standards.yml`) runs in `warn` mode
  (`.standards.mode`), not the ratchet's default `enforce`: at `enforce` it
  fails on two pre-existing `tsconfig.json` findings (TS-1, TS-2) this repo
  has not yet cleared. `warn` is `standards/docs/ratchet.md`'s prescribed
  first-adoption state, not a permanent exemption — clearing the findings and
  deleting the file is tracked as branchLeft/workspace#164.

## Stack secrets

This stack's secrets are wrapped by Pulumi's passphrase provider. Two values
make that work, and they are held as repository Actions secrets rather than
committed:

| Secret | What it is |
| --- | --- |
| `PULUMI_CONFIG_PASSPHRASE` | The passphrase itself. Pulumi reads it from the environment; nothing ever names it on a command line. |
| `PULUMI_SALT_BLOG` | The stack's `encryptionsalt`. The deploy job appends it to `Pulumi.blog.yaml` on the runner before any `pulumi` command, and never commits the result. |

**`Pulumi.blog.yaml` carries no `encryptionsalt`, and a commit that adds one is
rejected.** The salt is an offline verifier for the passphrase: anyone holding
it can test candidates at their own rate, with no state backend and no cloud
IAM in the loop to notice or rate-limit them. This repo is public, so that is
`branchLeft/standards` clause PUL-12's exact prohibition, and it hard-fails in
every mode with no exemption available. `scripts/assert-no-committed-pulumi-secrets.py`
is the mechanical check, because the salt is not added by hand: Pulumi writes
it back into the file itself during an ordinary `pulumi config set`, and the
diff then looks like exactly what the command was asked to do.

```bash
python3 scripts/assert-no-committed-pulumi-secrets.py --self-test
python3 scripts/assert-no-committed-pulumi-secrets.py --scan-tree .
python3 -m unittest discover -s scripts -p 'test_*.py'
```

**The `Committed-secret guard` job needs to be a required status check to
block anything.** Outside a ruleset it reports red and the merge goes through
anyway. It is deliberately not a job the deploy depends on: a salt already on
`main` is already in every clone, so refusing to apply would take the site
down without taking the salt back.

This tenant's passphrase is its own, and is never `ghost-platform`'s. A repo
holding a verifier for another repo's passphrase could attack it offline, so
the two are never interchangeable.

To apply by hand, append your own held copy of the salt to the working file and
do not commit it:

```bash
export PULUMI_CONFIG_PASSPHRASE='…'          # from the password manager
printf '\nencryptionsalt: %s\n' '…' >> Pulumi.blog.yaml
```

Then discard the change (`git checkout -- Pulumi.blog.yaml`) before committing
anything else from that tree.

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
three repo variables and one repo secret. On top of that one provisioning
secret, the deploy job requires two owner-seeded repository secrets —
`BLOG_MAIL_SMTP_PASSWORD` and `BLOG_BULK_EMAIL_API_KEY` — injected into the
stack config at runtime (see below); without them the deploy fails closed.

## Day-to-day

- CI (`.github/workflows/infra-ci.yml`) type-checks every pull request and
  applies `main` to the `blog` stack. Both jobs refuse to run if a
  template placeholder survives, and the deploy job's delete-guard preflight
  aborts any plan that would destroy this tenant's resources.
- Changes are pull requests against `Pulumi.blog.yaml` and `index.ts`.
- The two mail credentials (`mailSmtpPassword`, `bulkEmailApiKey`) are **not**
  committed to `Pulumi.blog.yaml`. They are held as repository Actions secrets
  and encrypted into the stack config by the deploy job at runtime, so no live
  credential — plaintext or KMS-wrapped — sits in this public tree. Any
  further secret value would follow the same pattern. The `secretsprovider`
  and `encryptedkey` in the stack file are a GCP-KMS-wrapped data key, not a
  credential, and are safe to commit.
- The mail and bulk-email config keys this stack consumes are the
  `blog-infra:mail*` and `blog-infra:bulkEmail*` values in `Pulumi.blog.yaml`;
  `GhostTenantMailArgs` and `GhostTenantBulkEmailArgs` in
  `@branchleft/ghost-platform-tenant` define what they become.

# Hedra developer documentation

Source for [Hedra's documentation](https://www.hedra.com/docs), built with
Mintlify. The docs focus on the v3 Developer platform, with legacy v2 resources
for existing integrations. Studio help lives under Resources alongside Legacy v2,
with no top-level product or landing-page promotion.

## Local preview

Install the current Mintlify CLI (`npm install -g mint`), then run `mint dev`
from this directory. Configuration lives in `docs.json`. Run `mint broken-links`
before submitting navigation changes.

## Content and API schemas

- `index.mdx`: developer landing page.
- `pages/developer/v3/`: current guides.
- `pages/app/`: Studio help, nested under Resources.
- `pages/developer/legacy/` and `pages/developer/guides/`: legacy v2 documentation.
- `openapi-v3.json`: generated v3 API contract and examples.
- `openapi.json`: generated legacy v2 contract.

The `Sync OpenAPI schemas` workflow refreshes both schemas. Put documentation
annotations in `openapi-v3-overrides.json` or `openapi-overrides.json` so they
survive regeneration. The workflow injects SDK samples and runs
`scripts/generate_v3_reference_nav.py` to regenerate v3 reference navigation.
The workflow requires the `OPENAPI_SYNC_TOKEN` repository secret with contents
and pull-request write access.
Run `python3 scripts/sync_openapi.py` to refresh `openapi.json` locally.

Studio help and legacy pages use `noindex`. Studio remains available under Resources
and through existing URLs, but is excluded from discovery and AI context. Generated
legacy operations use `x-mint.metadata` overrides. After deployment, check the emitted robots metadata,
search results, sitemap, and `llms.txt`; configuration alone is not proof of
indexing behavior. Preserve working legacy URLs while promoting v3.

## Publishing

The connected Mintlify deployment publishes changes to the default branch.
Review a preview and a pull request before merging. Local edits do not publish.

## Editing guidelines

Use current schemas and SDKs for examples. Distinguish generally available
features, research previews, and engineering-assisted deployments. Do not add
unreleased APIs, performance guarantees, or a legacy shutdown date without an
approved product source.

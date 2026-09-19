# M8 staging image

This directory packages the M8 staging runtime used for deployment validation.

## Source model

The canonical Threshold application remains in the repository's normal source tree.
M8 carries a frozen backend runtime archive plus a small set of staging hardening
overlays that were introduced during deployment validation.

The Docker image now consumes `threshold_m8_backend_runtime.tar.gz` directly.
Older Base64 chunk files were removed because they only reconstructed the same
archive and made the build harder to review.

The `apply_*.py` files are temporary compatibility overlays for the frozen M8
snapshot. They are intentionally explicit and fail when their expected source
markers are missing. New product development should target canonical source rather
than adding another overlay here.

## Verification

Build the staging image from the repository root with:

```bash
docker build -f deploy/m8/Dockerfile deploy/m8
```

Repository CI is expected to catch packaging regressions before this deployment
path is changed further.

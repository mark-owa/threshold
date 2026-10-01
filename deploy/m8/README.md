# Legacy M8 staging snapshot

This directory preserves the earlier M8 staging runtime for deployment compatibility.
Current application source is in `backend/` and `frontend/`. Builds from this
snapshot do not include later canonical changes.

## Source model

The canonical Threshold application remains in the repository's normal source tree.
M8 carries a frozen backend runtime archive plus a small set of staging hardening
overlays that were introduced during deployment validation.

The snapshot image consumes `threshold_m8_backend_runtime.tar.gz` directly.
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

Current repository CI validates canonical backend/frontend source and production
Compose syntax; it does not build this M8 image. A successful canonical CI run
therefore does not verify the archive or overlays. Add an image-build check and
compare the patched runtime with canonical source before further deployment changes.
See [verification evidence](../../docs/VERIFICATION.md).

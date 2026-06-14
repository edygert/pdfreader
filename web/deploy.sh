#!/usr/bin/env bash
# Deploy the PWA (this directory) to AWS S3, fronted by CloudFront for HTTPS.
#
# Why the two-pass sync + cache headers:
#   - vendor/ and icons/ are immutable (the SW serves them cache-first), so they
#     get a 1-year, immutable Cache-Control and can sit in CloudFront forever.
#   - The app shell (index.html, *.js, *.css, manifest) is network-first in the
#     SW; it gets no-cache so a redeploy is picked up on the next launch and
#     CloudFront never pins a stale service worker.
#   - .webmanifest needs an explicit Content-Type (the CLI guesses octet-stream,
#     which can stop Chrome offering install).
#
# Usage:
#   web/deploy.sh <bucket> [cloudfront-distribution-id]
#   # or via env:
#   PDFREADER_BUCKET=my-bucket PDFREADER_CF_DIST=E123... web/deploy.sh
#
# Config (env overrides, then positional args):
#   PDFREADER_BUCKET   S3 bucket name                 (required)
#   PDFREADER_CF_DIST  CloudFront distribution id     (optional; enables invalidation)
#   AWS_REGION         default: us-east-1
#   AWS_PROFILE        AWS CLI profile (optional; uses default credentials if unset)
#   DRY_RUN=1          show what would change, upload nothing

set -euo pipefail

WEB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BUCKET="${PDFREADER_BUCKET:-${1:-}}"
DISTRIBUTION_ID="${PDFREADER_CF_DIST:-${2:-}}"
REGION="${AWS_REGION:-us-east-1}"
PROFILE="${AWS_PROFILE:-}"

if [[ -z "$BUCKET" ]]; then
  echo "error: S3 bucket required (pass as \$1 or set PDFREADER_BUCKET)" >&2
  echo "usage: web/deploy.sh <bucket> [cloudfront-distribution-id]" >&2
  exit 2
fi

command -v aws >/dev/null 2>&1 || { echo "error: aws CLI not found" >&2; exit 1; }

AWS=(aws --region "$REGION")
[[ -n "$PROFILE" ]] && AWS+=(--profile "$PROFILE")
SYNC_OPTS=()
[[ "${DRY_RUN:-}" == "1" ]] && SYNC_OPTS+=(--dryrun)

# Never upload the scripts themselves or the README to the public site.
COMMON_EXCLUDES=(--exclude ".DS_Store" --exclude "deploy.sh" --exclude "bootstrap-aws.sh" --exclude "README.md")

echo "==> Deploying $WEB_DIR -> s3://$BUCKET  (region=$REGION${PROFILE:+ profile=$PROFILE})"

# Pass 1: immutable assets (vendor/, icons/) with a long, immutable cache.
# --delete is scoped by the include filters, so it only prunes removed
# vendor/icons objects — top-level app files are excluded and left untouched.
echo "==> [1/3] vendor/ + icons/  (cache-first, 1-year immutable)"
"${AWS[@]}" s3 sync "$WEB_DIR/" "s3://$BUCKET/" --delete \
  "${SYNC_OPTS[@]}" \
  --exclude "*" --include "vendor/*" --include "icons/*" \
  --cache-control "public, max-age=31536000, immutable"

# Pass 2: app shell with no-cache. --delete here prunes removed app files but
# excludes vendor/icons so it can't touch what pass 1 manages.
echo "==> [2/3] app shell  (network-first, no-cache)"
"${AWS[@]}" s3 sync "$WEB_DIR/" "s3://$BUCKET/" --delete \
  "${SYNC_OPTS[@]}" \
  "${COMMON_EXCLUDES[@]}" \
  --exclude "vendor/*" --exclude "icons/*" \
  --cache-control "no-cache"

# Pass 3: fix the manifest's Content-Type (and keep it no-cache).
if [[ "${DRY_RUN:-}" != "1" ]]; then
  echo "==> [3/3] manifest Content-Type -> application/manifest+json"
  "${AWS[@]}" s3 cp \
    "s3://$BUCKET/manifest.webmanifest" "s3://$BUCKET/manifest.webmanifest" \
    --metadata-directive REPLACE \
    --content-type "application/manifest+json" \
    --cache-control "no-cache"
else
  echo "==> [3/3] (dry run) skipping manifest Content-Type fix"
fi

# Invalidate only the network-first app shell at the edge; the immutable
# vendor/icons assets are intentionally left cached.
if [[ -n "$DISTRIBUTION_ID" && "${DRY_RUN:-}" != "1" ]]; then
  echo "==> CloudFront invalidation ($DISTRIBUTION_ID)"
  "${AWS[@]}" cloudfront create-invalidation \
    --distribution-id "$DISTRIBUTION_ID" \
    --paths "/" "/index.html" "/sw.js" "/app.js" "/styles.css" \
            "/pdf.js" "/state.js" "/shortcuts.js" "/manifest.webmanifest" \
    --query 'Invalidation.{Id:Id,Status:Status}' --output table
elif [[ -z "$DISTRIBUTION_ID" ]]; then
  echo "==> No CloudFront distribution id given — skipping invalidation."
  echo "    (pass it as \$2 or set PDFREADER_CF_DIST to invalidate the app shell)"
fi

echo "==> Done."

#!/usr/bin/env bash
# One-time AWS infra for the PWA: a private S3 bucket served over HTTPS by
# CloudFront via Origin Access Control (OAC). Idempotent — safe to re-run; it
# reuses the bucket/OAC/distribution if they already exist.
#
# After this completes, deploy the files with:
#   PDFREADER_CF_DIST=<distribution-id> web/deploy.sh <bucket>
#
# A custom domain is OPTIONAL. Without one you get a working
# https://<id>.cloudfront.net URL (fine for the PWA: HTTPS, installable, SW).
# To use a custom domain, first create+validate an ACM cert IN us-east-1
# (CloudFront requires that region), then pass its ARN:
#   DOMAIN=pdf.example.com ACM_CERT_ARN=arn:aws:acm:us-east-1:...:certificate/...
#
# Usage:
#   web/bootstrap-aws.sh <bucket>
#
# Config (env overrides, then positional args):
#   PDFREADER_BUCKET   S3 bucket name              (required)
#   DOMAIN             custom domain (CNAME)        (optional)
#   ACM_CERT_ARN       ACM cert ARN in us-east-1    (required iff DOMAIN set)
#   AWS_REGION         default: us-east-1
#   AWS_PROFILE        AWS CLI profile (optional; uses default credentials if unset)

set -euo pipefail

BUCKET="${PDFREADER_BUCKET:-${1:-}}"
REGION="${AWS_REGION:-us-east-1}"
PROFILE="${AWS_PROFILE:-}"
DOMAIN="${DOMAIN:-}"
ACM_CERT_ARN="${ACM_CERT_ARN:-}"
COMMENT="pdfreader PWA"
OAC_NAME="pdfreader-oac"
ORIGIN_ID="s3-$BUCKET"
# CloudFront managed cache policy "CachingOptimized": honors the origin's
# Cache-Control (so our no-cache app shell vs. immutable assets both work),
# clamped to [1s, 1y], with Gzip/Brotli.
CACHE_POLICY_ID="658327ea-f89d-4fab-a63d-7e88639e58f6"

if [[ -z "$BUCKET" ]]; then
  echo "error: S3 bucket required (pass as \$1 or set PDFREADER_BUCKET)" >&2
  echo "usage: web/bootstrap-aws.sh <bucket>" >&2
  exit 2
fi
command -v aws >/dev/null 2>&1 || { echo "error: aws CLI not found" >&2; exit 1; }
if [[ -n "$DOMAIN" && -z "$ACM_CERT_ARN" ]]; then
  echo "error: DOMAIN set but ACM_CERT_ARN missing (cert must be in us-east-1)" >&2
  exit 2
fi

AWS=(aws --region "$REGION")
[[ -n "$PROFILE" ]] && AWS+=(--profile "$PROFILE")
CFG="" ; POLICY=""
cleanup() { rm -f "${CFG:-}" "${POLICY:-}"; }
trap cleanup EXIT

echo "==> Bootstrapping  bucket=$BUCKET  region=$REGION${PROFILE:+  profile=$PROFILE}"

ACCOUNT_ID="$("${AWS[@]}" sts get-caller-identity --query Account --output text)"

# ---- 1. S3 bucket (private) ----
if "${AWS[@]}" s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "==> [1/5] bucket exists"
else
  echo "==> [1/5] creating bucket"
  # us-east-1 must NOT pass a LocationConstraint.
  "${AWS[@]}" s3api create-bucket --bucket "$BUCKET" >/dev/null
fi
"${AWS[@]}" s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# ---- 2. Origin Access Control ----
OAC_ID="$("${AWS[@]}" cloudfront list-origin-access-controls \
  --query "OriginAccessControlList.Items[?Name=='$OAC_NAME'].Id | [0]" --output text)"
if [[ -z "$OAC_ID" || "$OAC_ID" == "None" ]]; then
  echo "==> [2/5] creating OAC"
  OAC_ID="$("${AWS[@]}" cloudfront create-origin-access-control \
    --origin-access-control-config \
    "Name=$OAC_NAME,Description=pdfreader,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3" \
    --query OriginAccessControl.Id --output text)"
else
  echo "==> [2/5] OAC exists ($OAC_ID)"
fi

# ---- 3. CloudFront distribution ----
DIST_ID="$("${AWS[@]}" cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='$COMMENT'].Id | [0]" --output text 2>/dev/null || echo None)"

if [[ -n "$DIST_ID" && "$DIST_ID" != "None" ]]; then
  echo "==> [3/5] distribution exists ($DIST_ID)"
else
  echo "==> [3/5] creating distribution"
  ORIGIN_DOMAIN="$BUCKET.s3.$REGION.amazonaws.com"

  if [[ -n "$DOMAIN" ]]; then
    ALIASES_JSON="{\"Quantity\":1,\"Items\":[\"$DOMAIN\"]}"
    CERT_JSON="{\"ACMCertificateArn\":\"$ACM_CERT_ARN\",\"SSLSupportMethod\":\"sni-only\",\"MinimumProtocolVersion\":\"TLSv1.2_2021\"}"
  else
    ALIASES_JSON="{\"Quantity\":0}"
    CERT_JSON="{\"CloudFrontDefaultCertificate\":true}"
  fi

  CFG="$(mktemp)"
  cat >"$CFG" <<JSON
{
  "CallerReference": "pdfreader-$ACCOUNT_ID-$(date +%s)",
  "Comment": "$COMMENT",
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "HttpVersion": "http2and3",
  "PriceClass": "PriceClass_100",
  "Aliases": $ALIASES_JSON,
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "$ORIGIN_ID",
        "DomainName": "$ORIGIN_DOMAIN",
        "OriginPath": "",
        "CustomHeaders": { "Quantity": 0 },
        "OriginAccessControlId": "$OAC_ID",
        "S3OriginConfig": { "OriginAccessIdentity": "" },
        "OriginShield": { "Enabled": false }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "$ORIGIN_ID",
    "ViewerProtocolPolicy": "redirect-to-https",
    "Compress": true,
    "AllowedMethods": {
      "Quantity": 2,
      "Items": ["GET", "HEAD"],
      "CachedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] }
    },
    "CachePolicyId": "$CACHE_POLICY_ID"
  },
  "ViewerCertificate": $CERT_JSON
}
JSON

  DIST_ID="$("${AWS[@]}" cloudfront create-distribution \
    --distribution-config "file://$CFG" \
    --query Distribution.Id --output text)"
fi

# ---- 4. Bucket policy: allow only this distribution to read the bucket ----
echo "==> [4/5] bucket policy (CloudFront OAC read access)"
DIST_ARN="arn:aws:cloudfront::$ACCOUNT_ID:distribution/$DIST_ID"
POLICY="$(mktemp)"
cat >"$POLICY" <<JSON
{
  "Version": "2008-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontServicePrincipalReadOnly",
      "Effect": "Allow",
      "Principal": { "Service": "cloudfront.amazonaws.com" },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::$BUCKET/*",
      "Condition": { "StringEquals": { "AWS:SourceArn": "$DIST_ARN" } }
    }
  ]
}
JSON
"${AWS[@]}" s3api put-bucket-policy --bucket "$BUCKET" --policy "file://$POLICY"

# ---- 5. Report ----
DIST_DOMAIN="$("${AWS[@]}" cloudfront get-distribution \
  --id "$DIST_ID" --query Distribution.DomainName --output text)"

echo "==> [5/5] Done."
echo
echo "    Distribution ID : $DIST_ID"
echo "    CloudFront URL  : https://$DIST_DOMAIN"
[[ -n "$DOMAIN" ]] && echo "    Custom domain   : https://$DOMAIN  (point a CNAME at $DIST_DOMAIN)"
echo
echo "    A new distribution takes ~5-15 min to finish deploying."
echo "    Next:  PDFREADER_CF_DIST=$DIST_ID web/deploy.sh $BUCKET"

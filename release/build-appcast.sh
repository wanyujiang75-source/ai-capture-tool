#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT_DIR/macos-native/.build/artifacts/sparkle/Sparkle/bin"
APP_PATH="${1:?usage: build-appcast.sh app-path output-directory https-download-prefix}"
OUTPUT_DIR="${2:?missing output directory}"
DOWNLOAD_PREFIX="${3:?missing HTTPS download prefix}"
PLIST="$APP_PATH/Contents/Info.plist"

if [[ ! "$DOWNLOAD_PREFIX" =~ ^https://[a-zA-Z0-9.-]+(:[0-9]+)?/[^[:space:]]*/$ ]]; then
  echo "Sparkle download prefix must be an HTTPS URL ending in /" >&2
  exit 1
fi
if [[ -e "$OUTPUT_DIR" ]]; then
  echo "Update output already exists: $OUTPUT_DIR" >&2
  exit 1
fi

codesign --verify --deep --strict "$APP_PATH"
VERSION="$(plutil -extract CFBundleShortVersionString raw "$PLIST")"
BUILD_NUMBER="$(plutil -extract CFBundleVersion raw "$PLIST")"
if [[ ! "$VERSION" =~ ^[0-9]+[.][0-9]+[.][0-9]+$ || ! "$BUILD_NUMBER" =~ ^[1-9][0-9]*$ ]]; then
  echo "Invalid app version or build number" >&2
  exit 1
fi
if [[ "$(plutil -extract SURequireSignedFeed raw "$PLIST")" != "true" ]]; then
  echo "The app must require signed Sparkle feeds" >&2
  exit 1
fi

KEY_ARGS=(--account "${SPARKLE_KEYCHAIN_ACCOUNT:-ai-capture-updates}")
if [[ -n "${SPARKLE_PRIVATE_ED_KEY_FILE:-}" ]]; then
  KEY_ARGS=(--ed-key-file "$SPARKLE_PRIVATE_ED_KEY_FILE")
fi

mkdir -p "$(dirname "$OUTPUT_DIR")"
STAGING="$(mktemp -d "$(dirname "$OUTPUT_DIR")/.appcast.XXXXXX")"
trap 'rm -rf "$STAGING"' EXIT
ARCHIVE_NAME="AI-Capture-Update-$VERSION-arm64.zip"
ARCHIVE="$STAGING/$ARCHIVE_NAME"
FEED="$STAGING/appcast.xml"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ARCHIVE"

NOTES="$STAGING/${ARCHIVE_NAME%.zip}.md"
if [[ -n "${SPARKLE_RELEASE_NOTES:-}" ]]; then
  cp "$SPARKLE_RELEASE_NOTES" "$NOTES"
fi
"$TOOLS/generate_appcast" "${KEY_ARGS[@]}" --maximum-deltas 0 --embed-release-notes \
  --download-url-prefix "$DOWNLOAD_PREFIX" -o "$FEED" "$STAGING"

ITEM="/rss/channel/item"
ENCLOSURE="$ITEM/enclosure"
SIGNATURE="$(xmllint --nonet --xpath "string($ENCLOSURE/@*[local-name()='edSignature'])" "$FEED")"
if [[ -z "$SIGNATURE" ||
      "$(xmllint --nonet --xpath "string($ENCLOSURE/@url)" "$FEED")" != "$DOWNLOAD_PREFIX$ARCHIVE_NAME" ||
      "$(xmllint --nonet --xpath "string($ENCLOSURE/@length)" "$FEED")" != "$(stat -f %z "$ARCHIVE")" ||
      "$(xmllint --nonet --xpath "string($ITEM/*[local-name()='version'])" "$FEED")" != "$BUILD_NUMBER" ]]; then
  echo "Appcast does not match the signed update archive and app build" >&2
  exit 1
fi
"$TOOLS/sign_update" "${KEY_ARGS[@]}" --verify "$FEED"
"$TOOLS/sign_update" "${KEY_ARGS[@]}" --verify "$ARCHIVE" "$SIGNATURE"
rm -f "$NOTES"
mv "$STAGING" "$OUTPUT_DIR"

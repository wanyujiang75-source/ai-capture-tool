# macOS App Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate the approved “packet lens” artwork and make every built `AI抓包工具.app` expose it as a valid signed macOS application icon.

**Architecture:** Keep one version-controlled 1024px PNG as the visual source of truth. The existing native build script converts that source into a temporary complete iconset, compiles `AppIcon.icns`, embeds it before code signing, and declares it through `CFBundleIconFile`; packaging tests verify both the source contract and final bundle contract.

**Tech Stack:** Built-in `image_gen`, PNG alpha post-processing, macOS `sips`, `iconutil`, Bash, Python `unittest`/`plistlib`, `codesign`.

---

## File Map

- Create `macos-native/Resources/AppIcon.png`: approved 1024px packet-lens source artwork.
- Modify `macos-native/scripts/build-app.sh`: validate source, generate iconset/ICNS, embed the resource, and declare `CFBundleIconFile` before signing.
- Modify `tests/test_native_app_packaging.py`: validate source metadata and the generated bundle icon contract.
- Do not modify Web favicon, Swift view code, release naming, Android resources, runtime code, or capture behavior.

### Task 1: Lock and generate the source artwork

**Files:**
- Create: `macos-native/Resources/AppIcon.png`
- Modify: `tests/test_native_app_packaging.py:18-24`
- Modify: `tests/test_native_app_packaging.py:26-39`

- [ ] **Step 1: Write the failing source-asset test**

Add the source constant after the existing path constants:

```python
SOURCE_ICON = ROOT / "macos-native" / "Resources" / "AppIcon.png"
```

Add this test at the top of `NativeAppPackagingTests`:

```python
def test_source_icon_meets_asset_contract(self) -> None:
    self.assertTrue(SOURCE_ICON.is_file(), SOURCE_ICON)
    result = subprocess.run(
        [
            "sips",
            "-g",
            "pixelWidth",
            "-g",
            "pixelHeight",
            "-g",
            "hasAlpha",
            str(SOURCE_ICON),
        ],
        capture_output=True,
        text=True,
    )
    self.assertEqual(0, result.returncode, result.stderr)
    properties = {}
    for line in result.stdout.splitlines()[1:]:
        key, separator, value = line.strip().partition(": ")
        if separator:
            properties[key] = value
    self.assertEqual(
        {"pixelWidth": "1024", "pixelHeight": "1024", "hasAlpha": "yes"},
        properties,
    )
```

- [ ] **Step 2: Run the test and confirm the missing asset fails**

Run:

```bash
python -m unittest -v \
  tests.test_native_app_packaging.NativeAppPackagingTests.test_source_icon_meets_asset_contract
```

Expected: `FAIL` at `self.assertTrue(SOURCE_ICON.is_file(), SOURCE_ICON)` because the source PNG does not exist yet.

- [ ] **Step 3: Generate the approved artwork with the built-in image tool**

Use built-in `image_gen` with this exact production prompt:

```text
Use case: logo-brand
Asset type: macOS desktop application icon source artwork
Primary request: Create a professional app icon for a packet capture and network analysis tool.
Scene/backdrop: One centered macOS-style rounded-square icon placed on a perfectly flat solid #ff00ff chroma-key background for later background removal. The background must be one uniform color with no shadows, gradients, texture, reflections, floor plane, or lighting variation.
Subject: A thick white magnifying glass. Inside its lens, one cyan packet-flow path travels through three clean white circular network nodes.
Style/medium: Minimal geometric vector-like illustration, crisp edges, premium developer-tool aesthetic, no photorealism.
Composition/framing: Symmetrical centered composition, generous transparent-safe padding around the rounded square, strong silhouette that remains recognizable at 16px.
Lighting/mood: Flat controlled color with only a restrained deep-navy-to-electric-blue gradient inside the rounded-square body.
Color palette: deep navy #10213d, electric blue #0879e8, cyan #42d9ff, white; do not use magenta anywhere in the icon subject.
Constraints: no text, no letters, no robot, no brain, no shield, no bug, no extra symbols, no cast shadow, no contact shadow, no reflection, no watermark. Keep the magnifying glass and packet path visually distinct at small sizes.
Avoid: busy detail, thin strokes, glossy 3D rendering, generic AI sparkle motifs, purple gradients.
```

Save the generated image returned by the tool as `tmp/imagegen/AppIcon-chroma.png`, then remove the chroma background with the installed helper:

```bash
mkdir -p tmp/imagegen macos-native/Resources
python "${CODEX_HOME:-$HOME/.codex}/skills/.system/imagegen/scripts/remove_chroma_key.py" \
  --input tmp/imagegen/AppIcon-chroma.png \
  --out tmp/imagegen/AppIcon-transparent.png \
  --auto-key border \
  --soft-matte \
  --transparent-threshold 12 \
  --opaque-threshold 220 \
  --despill
sips -z 1024 1024 tmp/imagegen/AppIcon-transparent.png \
  --out macos-native/Resources/AppIcon.png >/dev/null
```

- [ ] **Step 4: Inspect the generated source before accepting it**

Open `macos-native/Resources/AppIcon.png` with `view_image` at original detail and verify all of the following:

- The rounded-square body has transparent corners and no magenta fringe.
- The white magnifying-glass silhouette is dominant.
- A cyan path and three white nodes are visible inside the lens.
- No text, letters, robot, brain, shield, bug, sparkle, purple gradient, or background shadow appears.
- At a 54px preview, the magnifying glass and packet path remain distinct.

If any item fails, perform one targeted built-in image edit that changes only the failed property, overwrite only `tmp/imagegen/AppIcon-transparent.png`, regenerate the 1024px final source, and repeat this checklist.

- [ ] **Step 5: Run the source test and commit the artwork contract**

Run:

```bash
python -m unittest -v \
  tests.test_native_app_packaging.NativeAppPackagingTests.test_source_icon_meets_asset_contract
```

Expected: `OK` with one passing test.

Commit:

```bash
git add macos-native/Resources/AppIcon.png tests/test_native_app_packaging.py
git commit -m "feat: add macOS packet lens icon artwork"
```

### Task 2: Lock the built application icon contract

**Files:**
- Modify: `tests/test_native_app_packaging.py:18-24`
- Modify: `tests/test_native_app_packaging.py:39-78`

- [ ] **Step 1: Add the final bundle icon test**

Add `plistlib` to the imports and add the expected iconset names near the constants:

```python
import plistlib

EXPECTED_ICONSET_FILES = [
    "icon_16x16.png",
    "icon_16x16@2x.png",
    "icon_32x32.png",
    "icon_32x32@2x.png",
    "icon_128x128.png",
    "icon_128x128@2x.png",
    "icon_256x256.png",
    "icon_256x256@2x.png",
    "icon_512x512.png",
    "icon_512x512@2x.png",
]
```

Add this test after `test_source_icon_meets_asset_contract`:

```python
def test_build_app_embeds_macos_icon(self) -> None:
    environment = {**os.environ, "EMBED_RUNTIME": "0"}
    subprocess.run(
        [str(BUILD_SCRIPT)],
        cwd=BUILD_SCRIPT.parents[1],
        env=environment,
        check=True,
    )
    info_plist = APP_PATH / "Contents" / "Info.plist"
    icon_path = APP_PATH / "Contents" / "Resources" / "AppIcon.icns"

    with info_plist.open("rb") as plist_file:
        bundle_properties = plistlib.load(plist_file)
    self.assertEqual("AppIcon", bundle_properties["CFBundleIconFile"])
    self.assertTrue(icon_path.is_file(), icon_path)

    with tempfile.TemporaryDirectory() as temporary_directory:
        iconset_path = Path(temporary_directory) / "AppIcon.iconset"
        result = subprocess.run(
            ["iconutil", "-c", "iconset", str(icon_path), "-o", str(iconset_path)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            sorted(EXPECTED_ICONSET_FILES),
            sorted(path.name for path in iconset_path.iterdir()),
        )
```

- [ ] **Step 2: Run the bundle test and confirm it fails**

Run:

```bash
python -m unittest -v \
  tests.test_native_app_packaging.NativeAppPackagingTests.test_build_app_embeds_macos_icon
```

Expected: `ERROR` for missing `CFBundleIconFile` or `FAIL` because `Contents/Resources/AppIcon.icns` does not exist.

### Task 3: Generate and embed `AppIcon.icns`

**Files:**
- Modify: `macos-native/scripts/build-app.sh:4-13`
- Modify: `macos-native/scripts/build-app.sh:25-29`
- Modify: `macos-native/scripts/build-app.sh:59-64`

- [ ] **Step 1: Define icon build paths**

Add these variables after `EMBED_RUNTIME`:

```bash
ICON_SOURCE="$ROOT_DIR/Resources/AppIcon.png"
ICONSET_DIR="$ROOT_DIR/build/AppIcon.iconset"
ICON_OUTPUT="$RESOURCES_DIR/AppIcon.icns"
```

- [ ] **Step 2: Add strict source/tool validation and iconset generation**

Insert this block immediately after copying the executable and before copying backend resources:

```bash
if [[ ! -f "$ICON_SOURCE" ]]; then
  echo "macOS app icon source not found: $ICON_SOURCE" >&2
  exit 1
fi
for command in sips iconutil; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "required macOS icon tool not found: $command" >&2
    exit 1
  fi
done

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"
while read -r filename pixels; do
  sips -z "$pixels" "$pixels" "$ICON_SOURCE" \
    --out "$ICONSET_DIR/$filename" >/dev/null
done <<'ICON_SIZES'
icon_16x16.png 16
icon_16x16@2x.png 32
icon_32x32.png 32
icon_32x32@2x.png 64
icon_128x128.png 128
icon_128x128@2x.png 256
icon_256x256.png 256
icon_256x256@2x.png 512
icon_512x512.png 512
icon_512x512@2x.png 1024
ICON_SIZES
iconutil -c icns "$ICONSET_DIR" -o "$ICON_OUTPUT"
rm -rf "$ICONSET_DIR"
```

- [ ] **Step 3: Declare the icon in `Info.plist`**

Add the following immediately after `CFBundleDisplayName` and before `CFBundlePackageType`:

```xml
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
```

- [ ] **Step 4: Run the focused bundle test**

Run:

```bash
python -m unittest -v \
  tests.test_native_app_packaging.NativeAppPackagingTests.test_build_app_embeds_macos_icon
```

Expected: `OK` with one passing test; `iconutil` can expand all ten expected iconset PNGs.

- [ ] **Step 5: Run the existing signature regression**

Run:

```bash
python -m unittest -v \
  tests.test_native_app_packaging.NativeAppPackagingTests.test_build_app_produces_a_valid_bundle_signature
```

Expected: `OK`; `codesign --verify --deep --strict` returns zero after the icon resource is embedded.

- [ ] **Step 6: Commit the build integration**

```bash
git add macos-native/scripts/build-app.sh tests/test_native_app_packaging.py
git commit -m "feat: embed macOS app icon"
```

### Task 4: Full packaging and visual acceptance

**Files:**
- Verify: `macos-native/Resources/AppIcon.png`
- Verify: `macos-native/build/AI抓包工具.app/Contents/Resources/AppIcon.icns`
- Verify: `macos-native/build/AI抓包工具.app/Contents/Info.plist`

- [ ] **Step 1: Run the relevant packaging test module**

Run:

```bash
python -m unittest -v tests.test_native_app_packaging
```

Expected: all tests in `NativeAppPackagingTests` pass, including source metadata, ICNS expansion, relocatable runtime, signing, development release, and notarization guards.

- [ ] **Step 2: Build the full desktop application**

Run:

```bash
macos-native/scripts/build-app.sh
```

Expected: prints the absolute `.app` path; the command exits zero after strict code-sign verification.

- [ ] **Step 3: Verify bundle metadata and icon resource**

Run:

```bash
plutil -extract CFBundleIconFile raw \
  macos-native/build/AI抓包工具.app/Contents/Info.plist
test -s macos-native/build/AI抓包工具.app/Contents/Resources/AppIcon.icns
codesign --verify --deep --strict --verbose=2 \
  macos-native/build/AI抓包工具.app
```

Expected: `plutil` prints `AppIcon`; the resource test exits zero; `codesign` reports `valid on disk` and `satisfies its Designated Requirement`.

- [ ] **Step 4: Inspect small-size icon renders**

Expand the final ICNS and create a contact sheet or inspect these four files with `view_image`:

```bash
rm -rf tmp/icon-qa/AppIcon.iconset
mkdir -p tmp/icon-qa
iconutil -c iconset \
  macos-native/build/AI抓包工具.app/Contents/Resources/AppIcon.icns \
  -o tmp/icon-qa/AppIcon.iconset
```

Inspect `icon_16x16.png`, `icon_32x32.png`, `icon_128x128.png`, and `icon_512x512.png`. Expected: no crop, magenta fringe, opaque corner, unreadable text, or missing lens/path silhouette.

- [ ] **Step 5: Perform Finder and Dock verification**

Quit any existing `AI抓包工具` instance through the app UI, launch the newly built bundle, and visually inspect Finder and Dock using Computer Use:

```bash
open -na macos-native/build/AI抓包工具.app
```

Expected: both Finder and Dock display the packet-lens icon instead of the generic macOS executable icon. Quit the verification instance normally so its embedded backend is cleaned up.

- [ ] **Step 6: Record completion evidence**

Mark task `A7` in `progress.md` as `DONE` after verification and record:

- Source PNG metadata result.
- Focused icon and signature test results.
- Full `tests.test_native_app_packaging` result.
- `plutil`/`codesign` output.
- Finder/Dock visual verification result.

Do not commit unrelated existing worktree modifications.

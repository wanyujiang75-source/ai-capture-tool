# Jenkins Package Source Design

## Goal
Connect AI抓包工具 to the company Jenkins REST API so the macOS desktop app can list enterprise build jobs, show each job's latest installable Android package, and install the selected package into the currently selected emulator.

## Context
- Jenkins is reachable at `http://192.168.77.150:8080`.
- The Jenkins account is username/password based and does not require an API token for this internal use case.
- Current job URLs returned by Jenkins use `http://192.168.3.22:8080/...`; the app must rewrite these to the configured base URL before API reads or artifact downloads.
- Existing package installation already supports `.apk`, `.apks`, and `.zip`, parses package metadata, rejects downgrades, archives the latest package, and updates the app library.

## Scope
- Add backend Jenkins package-source APIs.
- Add macOS native UI for listing Jenkins packages and installing one into the selected device.
- Reuse existing install logic after downloading the package to a temporary runtime directory.
- Do not trigger Jenkins builds.
- Do not modify Frida, mitmproxy, ADB capture, or emulator lifecycle logic.
- Do not store Jenkins credentials in git.

## Jenkins Selection Rules
The enterprise build list is computed from Jenkins jobs using these rules:
- Read all jobs from `/api/json?tree=jobs[name,url,color]`.
- Exclude disabled jobs.
- Exclude obvious automation/test jobs such as names containing `api-test`.
- For each remaining job, inspect recent builds and keep the newest successful build containing an `.apk`, `.apks`, or `.zip` artifact.
- Jobs without recent installable artifacts are omitted from the package list.

## Backend API
- `GET /api/package-sources/jenkins/packages`
  - Returns the filtered package list.
  - Each item includes job name, build number, result, build timestamp, artifact filename, artifact relative path, artifact URL, and inferred environment.
- `POST /api/package-sources/jenkins/install`
  - Request body: `device_id`, `job_name`, `build_number`, `artifact_relative_path`, `environment`.
  - Downloads the artifact with Jenkins credentials and no proxy for internal hosts.
  - Calls the same install helper used by manual uploads.

## Configuration
Configuration is read from environment variables first, then safe defaults:
- `JENKINS_BASE_URL`, default `http://192.168.77.150:8080`.
- `JENKINS_USERNAME`, default empty.
- `JENKINS_PASSWORD`, default empty.
- `JENKINS_JOB_EXCLUDE_KEYWORDS`, default `api-test`.
- `JENKINS_ARTIFACT_LIMIT`, default `10`.

## Native UI
The macOS app adds a Jenkins section inside the device/app page:
- Button to refresh Jenkins packages.
- List grouped by job name.
- Each package row shows app/job name, latest build number, artifact filename, build time, and install button.
- Install button uses the currently selected device and defaults to `test` environment.
- On install success, refresh apps and devices, then select the installed app when possible.

## Error Handling
- Jenkins unreachable: show a readable API error and keep existing app/device data usable.
- No artifact: omit the job from the package list.
- Download fails: return a backend error with job/build/artifact context.
- Emulator not ready or active capture running: reuse existing install prechecks and messages.
- Package install fails: reuse existing `adb install` error response.

## Verification
- Jenkins package list returns Melody, PokeHub, and Stickerhub latest APKs when reachable.
- `swift build` passes.
- Existing web upload tests still pass.
- Backend route can fetch package list without using the system proxy.

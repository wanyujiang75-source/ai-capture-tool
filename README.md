# AI抓包工具

Local Web console for long-lived Android packet capture and API analysis.

This workspace contains helper scripts and a retained daily-use Android emulator
based on:

- Retained Android capture AVD: `Medium_Phone_API_36.1`
- Legacy rootable lab AVD: `lab-android35-gapi`
- `mitmweb` on host ports `9090` and `9091`
- mitmweb UI token: `android-capture`
- Android global proxy: `10.0.2.2:9090`
- Android global proxy setup for the retained Google Play emulator
- Optional temporary system CA overlay for rootable lab emulators
- Maestro for Playwright-style Android UI automation

The Google Play emulator is a non-root production build. It keeps installed apps
and Google account state, but HTTPS decryption may require a user CA install and
some apps may still reject interception because of certificate pinning.

Emulator app data is persistent as long as you keep using the same AVD and do
not wipe or delete it. The retained Android emulator for everyday use and
capture is `Medium_Phone_API_36.1`; installed apps and the Google account should
continue to exist there across restarts.

## Prerequisites

- Android SDK at `$HOME/Library/Android/sdk`
- An existing Google Play AVD named `Medium_Phone_API_36.1`
- Optional rootable lab AVD named `lab-android35-gapi`
- `adb`, `openssl`, and `mitmweb` available on the host
- Optional Android UI automation: `maestro`

## Typical flow

Start the Web backend and frontend only:

`./start_capture.sh`

Then open the frontend page:

`http://127.0.0.1:7002`

Daily operation is handled in the Web page:

1. Click `启动模拟器` to start the retained AVD from the page.
2. Add or select the target Android app.
3. Click `按默认模式启动`, `system`, or `flutter-socks` to start capture.
4. Operate the app manually in the emulator.
5. Use the interface analysis panel to view request/response data and export cURL.

The Web console is the recommended long-term entrypoint. It keeps an app library,
starts and stops one capture session at a time, links to mitmweb, indexes
`runtime/captures/<session>/candidates.tsv`, and shows full request/response
details with cURL export. It still delegates capture work to the existing
`ai_capture.sh`, `ai_capture_stop.sh`, `ai_capture_status.sh`, mitmproxy, and
Frida scripts instead of replacing them.

Console capture task records are project-run scoped. When the Web service is
closed and started again, the page clears previous capture link/interface
records from SQLite while keeping the app library and raw files under
`runtime/captures/`.

`./start_capture.sh` is now a Web service launcher. It does not start the
emulator and does not start packet capture automatically.

Services:

- Frontend: `http://127.0.0.1:7002`
- Backend API: `http://127.0.0.1:7001`

Stop the Web services:

`./scripts/stop_web_services.sh`

If you intentionally need the old direct CLI capture flow, use:

`./scripts/ai_capture.sh android`

If `npm` is available, the frontend dev service is started from `web/`. If you
only need the backend-served built production UI, run `./scripts/start_console.sh`
and open `http://127.0.0.1:7001`.

Do not pass a target URL to the discovery launcher. Start capture, operate any
app on the emulator, then read the discovered likely business APIs from:

- `runtime/captures/ai-discover-*/summary.md`
- `runtime/captures/ai-discover-*/candidates.tsv`
- `runtime/captures/ai-discover-*/*.request.*`
- `runtime/captures/ai-discover-*/*.response.*`

Check or stop the current discovery worker:

`./scripts/ai_capture_status.sh`

`./scripts/ai_capture_stop.sh`

Compatibility Android proxy setup on the retained emulator:

`./scripts/play_capture_up.sh`

Prepare a user CA manually only if you intentionally use a non-root emulator:

`./scripts/install_play_user_ca.sh`

Run a Maestro UI automation flow on the Play emulator:

`./scripts/maestro_run.sh`

1. Bring the whole lab up in one command:

   `./scripts/lab_up.sh`

Everyday Android emulator:

`./scripts/start_android_emulator.sh`

Compatibility launcher for the retained Android AVD:

`./scripts/start_play_emulator.sh`

2. Or run the individual steps:

   Start the emulator:

   `./scripts/start_lab_emulator.sh`

3. Start mitmweb:

   `./scripts/start_mitm_stack.sh`

4. Point Android at the host proxy:

   `./scripts/apply_android_proxy.sh`

5. Inject the mitmproxy CA into the emulator trust store:

   `./scripts/install_mitm_system_ca.sh`

6. Verify the environment:

   `./scripts/verify_lab.sh`

7. Optionally start Frida on the emulator for pinning bypass work:

   `./scripts/start_frida_server.sh`

8. Stop Frida when you no longer need it:

   `./scripts/stop_frida_server.sh`

9. Tear the lab down when needed:

   `./scripts/lab_down.sh`

## User CA fallback

The default retained emulator `Medium_Phone_API_36.1` is non-root, so use this
flow when HTTPS decryption is needed and the app trusts user CAs.

1. Start the Play capture flow:

   `./scripts/play_capture_up.sh`

2. If the emulator was reset or the user CA is missing, prepare the CA:

   `./scripts/install_play_user_ca.sh`

3. Finish the Android Settings prompts on the emulator:

   `More security & privacy -> Encryption & credentials -> Install a certificate -> CA certificate`

4. Accept `INSTALL ANYWAY`, enter PIN `0000`, then choose
   `Downloads/mitmproxy-ca-cert.cer.crt`.

5. Verify it under:

   `Settings -> Trusted credentials -> User -> mitmproxy`

Some apps and Google services may still reject HTTPS interception even with the
user CA installed because they pin certificates or do not trust user CAs.

## Android UI automation

Maestro is installed as the high-level Android automation layer, similar in use
to Playwright for web flows.

Run the sample Chrome flow:

`./scripts/maestro_run.sh`

Launch StickerHub through Maestro:

`./scripts/maestro_run.sh maestro/flows/open-stickerhub.yaml`

Run a custom flow:

`./scripts/maestro_run.sh maestro/flows/open-app.yaml`

For `open-app.yaml`, pass the target package:

`APP_ID=com.example.app ./scripts/maestro_run.sh maestro/flows/open-app.yaml`

## Persistent app workflow

Keep `Medium_Phone_API_36.1` as the retained daily driver and archive app
installers locally only when you need a backup installer.

1. Use the retained Android AVD for long-lived installs and account login:

   `./scripts/start_play_emulator.sh`

2. Archive an installed app from the current device into the workspace:

   `./scripts/archive_installed_app.sh com.meta.inno.sticker stickerhub`

3. List archived installers:

   `./scripts/list_archived_apps.sh`

4. Reinstall an archived app onto the currently selected emulator:

   `./scripts/install_archived_app.sh stickerhub`

Archived split APKs are stored under `runtime/apks/<archive-name>/` with a
`metadata.txt` file that records package name, version, and launcher activity.

## Notes

- The mitmproxy web UI listens on
  `http://127.0.0.1:9091/?token=android-capture`.
- The proxy listener is `10.0.2.2:9090` from inside the emulator.
- `./start_capture.sh` starts only the Web backend/frontend services. Emulator
  startup and capture startup are explicit actions in the Web page.
- The active `Android` capture path targets `Medium_Phone_API_36.1`, the retained
  emulator that keeps your installed apps and Google account.
- The AI discovery flow captures first and discovers URLs afterward. It filters
  out common Google, connectivity, ad, crash, and analytics noise, then groups
  remaining app traffic by similar URL patterns.
- The `iOS` path is currently kept as a reserved entry only. The active
  automated capture flow is `Android`.
- Use `Medium_Phone_API_36.1` as the default retained Android emulator for future
  app installs, login flows, and anything that should keep app data.
- `./scripts/play_capture_up.sh` and `./scripts/start_play_emulator.sh` are
  compatibility entrypoints and now default to `Medium_Phone_API_36.1`.
- On rootable lab emulators, the system CA overlay is temporary; rerun
  `./scripts/install_mitm_system_ca.sh` after each emulator reboot.
- On macOS, the emulator launch script opens a new Terminal window.
- On macOS, `mitmweb` prefers a detached `screen` session instead of a GUI Terminal.
- All Android-side scripts accept `ADB_SERIAL=<serial>` if you want to pin them to
  a specific emulator or physical device.
- The CA installer also overlays the `com.android.networkstack.process` mount
  namespace so Android's own connectivity checks do not falsely show "No internet"
  while the global proxy is enabled.
- To clear the Android proxy manually:

  `adb shell settings put global http_proxy :0`

- Chrome first-run traffic and some Google endpoints may still fail TLS inspection even
  when the lab is configured correctly. Treat those as noise unless you are
  specifically testing Google services.
- App-specific legacy captures such as PokeHub use mitmproxy `ignore_hosts` passthrough for Google
  auth plus ad/analytics SDK domains such as AppLovin/Applvn, UnityAds, Facebook,
  DoubleClick, Adjust, Axon, Firebase logging/in-app messaging/remote config.
  Those connections are forwarded without decryption so the proxy view stays
  focused on app feature traffic.

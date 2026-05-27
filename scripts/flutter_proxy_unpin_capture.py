#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import time

try:
    import frida
except ImportError as exc:
    print(f"frida Python package is required: {exc}", file=sys.stderr)
    sys.exit(1)


DEFAULT_PACKAGE = "com.meta.inno.monopoly_sticker"
DEFAULT_ACTIVITY = "com.meta.inno.monopoly_sticker/.MainActivity"


SETENV_SCRIPT = r"""
(() => {
  const envValues = JSON.parse('%ENV_JSON%');
  const setenvPtr = Module.findGlobalExportByName("setenv");
  if (!setenvPtr) {
    send({type: "setenv", status: "missing"});
    return;
  }
  const setenv = new NativeFunction(setenvPtr, "int", ["pointer", "pointer", "int"]);
  Object.keys(envValues).forEach((name) => {
    const rc = setenv(Memory.allocUtf8String(name), Memory.allocUtf8String(envValues[name]), 1);
    send({type: "setenv", name, value: envValues[name], rc});
  });
})();
"""


FORCE_FLUTTER_CERT_OK_SCRIPT = r"""
(() => {
  const ARM64_CERT_CALLBACK_PATTERNS = [
    "ff c3 00 d1 fe 57 01 a9 f4 4f 02 a9 1f 04 00 71 c0 07 00 54 f3 03 01 aa ?? ?? ?? 94",
    "ff c3 00 d1 fe 57 01 a9 f4 4f 02 a9 1f 04 00 71 c0 02 00 54 f3 03 01 aa ?? ?? ?? 94"
  ];
  const ARM64_SSL_VERIFY_PEER_CERT_PATTERNS = [
    "F? 0F 1C F8 F? 5? 01 A9 F? 5? 02 A9 F? ?? 03 A9 ?? ?? ?? ?? 68 1A 40 F9",
    "F? 43 01 D1 FE 67 01 A9 F8 5F 02 A9 F6 57 03 A9 F4 4F 04 A9 13 00 40 F9 F4 03 00 AA 68 1A 40 F9",
    "FF 43 01 D1 FE 67 01 A9 ?? ?? 06 94 ?? 7? 06 94 68 1A 40 F9 15 15 41 F9 B5 00 00 B4 B6 4A 40 F9",
    "FF ?3 01 D1 F? ?? 01 A9 ?? ?? ?? 94 ?? ?? ?? 52 48 00 00 39 1A 50 40 F9 DA 02 00 B4 48 03 40 F9"
  ];
  const hooked = {};

  function hookCandidate(address, source) {
    const key = address.toString();
    if (hooked[key]) return;
    hooked[key] = true;
    try {
      Interceptor.attach(address, {
        onLeave(retval) {
          if (retval.toInt32() !== 1) {
            send({type: "flutter-cert-bypass-hit", address: key, old: retval.toInt32()});
          }
          retval.replace(1);
        }
      });
      send({type: "flutter-cert-bypass-hooked", address: key, source});
    } catch (e) {
      send({type: "flutter-cert-bypass-error", address: key, source, error: String(e)});
    }
  }

  function replaceVerifyPeerCert(address, source) {
    const key = "verify:" + address.toString();
    if (hooked[key]) return;
    hooked[key] = true;
    try {
      Interceptor.replace(address, new NativeCallback(function(pathPtr, flags) {
        send({type: "flutter-ssl-verify-peer-cert-hit", address: address.toString(), flags: flags});
        return %FLUTTER_VERIFY_SUCCESS_VALUE%;
      }, "int", ["pointer", "int"]));
      send({type: "flutter-ssl-verify-peer-cert-hooked", address: address.toString(), source});
    } catch (e) {
      send({type: "flutter-ssl-verify-peer-cert-error", address: address.toString(), source, error: String(e)});
    }
  }

  function patchFlutter(module) {
    if (Process.arch !== "arm64") {
      send({type: "flutter-cert-bypass-error", error: "only arm64 implemented", arch: Process.arch});
      return;
    }
    const ranges = Process.enumerateRanges("r-x").filter((range) => {
      return range.base.compare(module.base) >= 0 &&
        range.base.compare(module.base.add(module.size)) < 0;
    });
    let total = 0;
    for (const range of ranges) {
      for (const pattern of ARM64_CERT_CALLBACK_PATTERNS) {
        const matches = Memory.scanSync(range.base, range.size, pattern);
        for (const match of matches) {
          total++;
          hookCandidate(match.address, pattern);
        }
      }
      for (const pattern of ARM64_SSL_VERIFY_PEER_CERT_PATTERNS) {
        const matches = Memory.scanSync(range.base, range.size, pattern);
        for (const match of matches) {
          total++;
          replaceVerifyPeerCert(match.address, pattern);
        }
      }
    }
    send({type: "flutter-cert-bypass-ready", module: module.name, base: module.base.toString(), size: module.size, candidates: total});
  }

  let attempts = 0;
  const timer = setInterval(() => {
    attempts++;
    const flutter = Process.findModuleByName("libflutter.so");
    if (!flutter) {
      if (attempts % 20 === 0) {
        send({type: "flutter-cert-bypass-waiting", attempts});
      }
      return;
    }
    clearInterval(timer);
    patchFlutter(flutter);
  }, 250);
})();
"""


def now_label():
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def adb_binary():
    sdk_root = os.environ.get("ANDROID_SDK_ROOT") or os.path.expanduser("~/Library/Android/sdk")
    candidate = os.path.join(sdk_root, "platform-tools", "adb")
    return candidate if os.path.exists(candidate) else "adb"


def adb(serial, args, check=True):
    cmd = [adb_binary(), "-s", serial, *args]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"adb failed: {' '.join(cmd)}")
    return proc.stdout.strip()


def wait_for_pid(serial, package, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        pid = current_pid(serial, package)
        if pid:
            return pid
        time.sleep(0.1)
    raise RuntimeError(f"timed out waiting for pid: {package}")


def current_pid(serial, package):
    out = adb(serial, ["shell", "pidof", "-s", package], check=False).replace("\r", "").strip()
    if not out:
        return None
    try:
        return int(out.split()[0])
    except (TypeError, ValueError):
        return None


def needs_reattach(*, attached_pid, current_pid, detached):
    if not current_pid:
        return False
    if not attached_pid:
        return True
    return bool(detached or attached_pid != current_pid)


def read_text(path):
    with open(path, "r", encoding="utf-8") as fp:
        return fp.read()


def build_config(repo_dir, cert_pem, proxy_host, proxy_port, debug, socks5=False):
    source = read_text(os.path.join(repo_dir, "config.js"))
    start = source.index("const CERT_PEM = `")
    cert_start = source.index("`", start) + 1
    cert_end = source.index("`;", cert_start)
    source = source[:cert_start] + cert_pem.strip() + source[cert_end:]
    source = source.replace("const PROXY_HOST = '127.0.0.1';", f"const PROXY_HOST = '{proxy_host}';")
    source = source.replace("const PROXY_PORT = 8000;", f"const PROXY_PORT = {int(proxy_port)};")
    source = source.replace("const DEBUG_MODE = false;", f"const DEBUG_MODE = {'true' if debug else 'false'};")
    source = source.replace("const PROXY_SUPPORTS_SOCKS5 = false;", f"const PROXY_SUPPORTS_SOCKS5 = {'true' if socks5 else 'false'};")
    return source


def build_combined_script(args):
    repo_dir = args.httptoolkit_dir
    cert_pem = read_text(args.cert)
    parts = []
    if not args.no_proxy_env:
        proxy = f"http://{args.proxy_host}:{args.proxy_port}"
        env = {
            "HTTP_PROXY": proxy,
            "HTTPS_PROXY": proxy,
            "http_proxy": proxy,
            "https_proxy": proxy,
            "NO_PROXY": "localhost,127.0.0.1,::1",
            "no_proxy": "localhost,127.0.0.1,::1",
        }
        env_script = SETENV_SCRIPT.replace(
            "%ENV_JSON%",
            json.dumps(env).replace("\\", "\\\\").replace("'", "\\'"),
        )
        parts.append(env_script)
    if args.native_connect_hook or args.native_tls_hook:
        parts.append(build_config(repo_dir, cert_pem, args.proxy_host, args.proxy_port, args.debug, socks5=args.socks5))
    if args.native_connect_hook:
        parts.append(read_text(os.path.join(repo_dir, "native-connect-hook.js")))
    if args.native_tls_hook:
        parts.append(read_text(os.path.join(repo_dir, "native-tls-hook.js")))
    parts.append(FORCE_FLUTTER_CERT_OK_SCRIPT.replace(
        "%FLUTTER_VERIFY_SUCCESS_VALUE%",
        str(int(args.flutter_verify_success_value)),
    ))
    return "\n\n".join(parts)


def main():
    root = os.getcwd()
    parser = argparse.ArgumentParser(description="Run a Flutter Android app through mitmproxy with Frida proxy env + certificate bypass hooks.")
    parser.add_argument("--serial", default=os.environ.get("ADB_SERIAL") or "emulator-5554")
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--activity", default=DEFAULT_ACTIVITY)
    parser.add_argument("--proxy-host", default="10.0.2.2")
    parser.add_argument("--proxy-port", default="9090")
    parser.add_argument("--frida-host", default="127.0.0.1:27042", help="Frida remote device endpoint. Use the emulator-specific adb forward to avoid attaching to another USB device.")
    parser.add_argument("--cert", default=os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.pem"))
    parser.add_argument("--httptoolkit-dir", default=os.path.join(root, "tools", "httptoolkit-frida"))
    parser.add_argument("--outdir", default=os.path.join(root, "runtime", "captures", f"flutter-proxy-unpin-{now_label()}"))
    parser.add_argument("--no-force-stop", action="store_true")
    parser.add_argument("--no-proxy-env", action="store_true", help="Do not inject HTTP_PROXY/HTTPS_PROXY. Use this with SOCKS5 native transparent redirection to avoid protocol conflicts.")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--native-tls-hook", action="store_true", help="Also load HTTP Toolkit native TLS hook. Usually not needed for Flutter dart:io.")
    parser.add_argument("--native-connect-hook", action="store_true", help="Redirect app TCP connect() calls to the proxy.")
    parser.add_argument("--socks5", action="store_true", help="Use SOCKS5 handshakes in native-connect-hook so mitmproxy sees the original destination.")
    parser.add_argument("--flutter-verify-success-value", type=int, choices=(0, 1), default=0, help="Return value used by the Flutter ssl_verify_peer_cert hook.")
    parser.add_argument("--duration", type=int, default=0, help="Seconds to keep hooks alive. 0 means until Ctrl-C.")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    log_path = os.path.join(args.outdir, "frida-unpin.log")
    last_path = os.path.join(root, "runtime", "last-flutter-proxy-unpin-dir.txt")
    with open(last_path, "w", encoding="utf-8") as fp:
        fp.write(args.outdir + "\n")

    def log(line):
        print(line, flush=True)
        with open(log_path, "a", encoding="utf-8") as fp:
            fp.write(line + "\n")

    if not args.no_force_stop:
        adb(args.serial, ["shell", "am", "force-stop", args.package], check=False)
        time.sleep(0.5)

    adb(args.serial, ["shell", "am", "start", "-n", args.activity])
    pid = wait_for_pid(args.serial, args.package)
    log(f"started package={args.package} pid={pid} proxy=http://{args.proxy_host}:{args.proxy_port}")

    def on_message(message, data):
        del data
        if message.get("type") == "send":
            log(json.dumps(message.get("payload") or {}, ensure_ascii=False))
        elif message.get("type") == "error":
            log(json.dumps(message, ensure_ascii=False))
        else:
            log(json.dumps(message, ensure_ascii=False))

    if args.frida_host:
        device = frida.get_device_manager().add_remote_device(args.frida_host)
    else:
        device = frida.get_usb_device(timeout=10)

    script_source = build_combined_script(args)
    state = {"session": None, "script": None, "pid": None, "detached": False}

    def detach_current():
        if state["session"] is None:
            return
        try:
            state["session"].detach()
        except Exception:
            pass
        state["session"] = None
        state["script"] = None
        state["pid"] = None
        state["detached"] = False

    def attach_to_pid(target_pid):
        detach_current()
        session = device.attach(target_pid)

        def on_detached(reason, crash=None):
            state["detached"] = True
            log(f"frida session detached pid={target_pid} reason={reason} crash={crash or ''}".rstrip())

        try:
            session.on("detached", on_detached)
        except Exception:
            pass
        script = session.create_script(script_source)
        script.on("message", on_message)
        script.load()
        state["session"] = session
        state["script"] = script
        state["pid"] = target_pid
        state["detached"] = False
        log(f"frida hooks loaded pid={target_pid}; keep this process running while capturing")

    attach_to_pid(pid)

    stop = {"value": False}

    def handle_stop(_signum, _frame):
        stop["value"] = True

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    started = time.time()
    try:
        while not stop["value"]:
            if args.duration and time.time() - started >= args.duration:
                break
            pid_now = current_pid(args.serial, args.package)
            if needs_reattach(attached_pid=state["pid"], current_pid=pid_now, detached=state["detached"]):
                log(f"reattaching frida hooks old_pid={state['pid']} current_pid={pid_now} detached={state['detached']}")
                try:
                    attach_to_pid(pid_now)
                except Exception as exc:
                    log(f"reattach failed pid={pid_now}: {exc}")
                    time.sleep(1.0)
                    continue
            time.sleep(0.75)
    finally:
        detach_current()
        log("frida hooks detached")


if __name__ == "__main__":
    main()

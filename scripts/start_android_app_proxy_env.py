#!/usr/bin/env python3
import argparse
import json
import os
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
        out = adb(serial, ["shell", "pidof", "-s", package], check=False).replace("\r", "").strip()
        if out:
            return int(out.split()[0])
        time.sleep(0.1)
    raise RuntimeError(f"timed out waiting for pid: {package}")


SETENV_AND_GETENV_LOGGER = r"""
const envValues = JSON.parse('%ENV_JSON%');
const proxyNames = {
  "HTTP_PROXY": true,
  "HTTPS_PROXY": true,
  "http_proxy": true,
  "https_proxy": true,
  "NO_PROXY": true,
  "no_proxy": true
};

function installEnv() {
  const setenvPtr = Module.findGlobalExportByName("setenv");
  if (!setenvPtr) {
    send({type: "setenv", status: "missing"});
    return;
  }
  const setenv = new NativeFunction(setenvPtr, "int", ["pointer", "pointer", "int"]);
  for (const name in envValues) {
    const rc = setenv(Memory.allocUtf8String(name), Memory.allocUtf8String(envValues[name]), 1);
    send({type: "setenv", name: name, value: envValues[name], rc: rc});
  }
}

function hookGetenv() {
  const addr = Module.findGlobalExportByName("getenv");
  if (!addr) {
    send({type: "getenv-hook", status: "missing"});
    return;
  }
  Interceptor.attach(addr, {
    onEnter(args) {
      this.name = args[0].readCString();
    },
    onLeave(retval) {
      if (proxyNames[this.name]) {
        send({
          type: "getenv",
          name: this.name,
          value: retval.isNull() ? "" : retval.readCString()
        });
      }
    }
  });
  send({type: "getenv-hook", status: "installed"});
}

installEnv();
hookGetenv();
"""


def main():
    parser = argparse.ArgumentParser(description="Start an Android app through Frida with HTTP proxy environment variables.")
    parser.add_argument("--serial", default=os.environ.get("ADB_SERIAL") or "emulator-5554")
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--activity", default=DEFAULT_ACTIVITY)
    parser.add_argument("--proxy-host", default="10.0.2.2")
    parser.add_argument("--proxy-port", default="9090")
    parser.add_argument("--no-force-stop", action="store_true")
    parser.add_argument("--detach-delay", type=float, default=8.0)
    args = parser.parse_args()

    proxy = f"http://{args.proxy_host}:{args.proxy_port}"
    env = {
        "HTTP_PROXY": proxy,
        "HTTPS_PROXY": proxy,
        "http_proxy": proxy,
        "https_proxy": proxy,
        "NO_PROXY": "localhost,127.0.0.1,::1",
        "no_proxy": "localhost,127.0.0.1,::1",
    }

    if not args.no_force_stop:
        adb(args.serial, ["shell", "am", "force-stop", args.package], check=False)
        time.sleep(0.5)

    device = frida.get_usb_device(timeout=10)
    spawned = True
    try:
        pid = device.spawn([args.package])
    except Exception as exc:
        spawned = False
        print(f"spawn unavailable, falling back to adb start + attach: {type(exc).__name__}: {exc}", flush=True)
        adb(args.serial, ["shell", "am", "start", "-n", args.activity])
        pid = wait_for_pid(args.serial, args.package)
    session = device.attach(pid)

    def on_message(message, data):
        if message.get("type") == "send":
            print(json.dumps(message.get("payload") or {}, ensure_ascii=False), flush=True)
        else:
            print(json.dumps(message, ensure_ascii=False), flush=True)

    script_source = SETENV_AND_GETENV_LOGGER.replace(
        "%ENV_JSON%",
        json.dumps(env).replace("\\", "\\\\").replace("'", "\\'"),
    )
    script = session.create_script(script_source)
    script.on("message", on_message)
    script.load()
    if spawned:
        device.resume(pid)

    print(f"started package={args.package} pid={pid} proxy={proxy}", flush=True)
    time.sleep(args.detach_delay)
    session.detach()
    print("detached; app keeps running with proxy environment", flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import re
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
DEFAULT_FILTER = (
    r"blockdance|aisong|/portal/|HTTP/|POST |GET |PUT |PATCH |DELETE |"
    r"content-type|application/json|^\s*[\{\[]"
)


def now_label():
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def adb_binary():
    sdk_root = os.environ.get("ANDROID_SDK_ROOT") or os.path.expanduser("~/Library/Android/sdk")
    candidate = os.path.join(sdk_root, "platform-tools", "adb")
    return candidate if os.path.exists(candidate) else "adb"


def adb(args, serial=None, check=True):
    cmd = [adb_binary()]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"adb failed: {' '.join(cmd)}")
    return proc.stdout.strip()


def resolve_pid(serial, package, activity=None, launch=False):
    out = adb(["shell", "pidof", "-s", package], serial=serial, check=False).replace("\r", "").strip()
    if out:
        return int(out.split()[0])
    if not launch:
        raise RuntimeError(f"package is not running: {package}")
    if activity:
        adb(["shell", "am", "start", "-n", activity], serial=serial)
    else:
        adb(["shell", "monkey", "-p", package, "1"], serial=serial)
    deadline = time.time() + 20
    while time.time() < deadline:
        out = adb(["shell", "pidof", "-s", package], serial=serial, check=False).replace("\r", "").strip()
        if out:
            return int(out.split()[0])
        time.sleep(0.5)
    raise RuntimeError(f"timed out waiting for package pid: {package}")


def is_mostly_text(data):
    if not data:
        return False
    printable = 0
    for b in data:
        if b in (9, 10, 13) or 32 <= b <= 126:
            printable += 1
    return printable / max(len(data), 1) >= 0.70


def to_text(data):
    return data.decode("utf-8", errors="replace")


def safe_slug(value, max_len=72):
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return (value or "chunk")[:max_len]


FRIDA_SCRIPT = r"""
const config = JSON.parse('%CONFIG_JSON%');
const maxBytes = config.maxBytes;
const captureAll = config.captureAll;
const filter = new RegExp(config.filter, 'i');
const hooked = {};
const interestingHandles = {};

function moduleContains(module, ptrValue) {
  try {
    return ptrValue.compare(module.base) >= 0 && ptrValue.compare(module.base.add(module.size)) < 0;
  } catch (e) {
    return false;
  }
}

function bytesToPreview(ptrValue, len) {
  const cap = Math.min(len, 4096);
  if (cap <= 0) return "";
  let arrayBuffer;
  try {
    arrayBuffer = Memory.readByteArray(ptrValue, cap);
  } catch (e) {
    return "";
  }
  const bytes = new Uint8Array(arrayBuffer);
  let out = "";
  let printable = 0;
  for (let i = 0; i < bytes.length; i++) {
    const b = bytes[i];
    if (b === 9) {
      out += "\t";
      printable++;
    } else if (b === 10) {
      out += "\n";
      printable++;
    } else if (b === 13) {
      out += "\r";
      printable++;
    } else if (b >= 32 && b <= 126) {
      out += String.fromCharCode(b);
      printable++;
    } else {
      out += ".";
    }
  }
  return out;
}

function shouldCapture(handle, preview) {
  const now = Date.now();
  const key = handle ? handle.toString() : "none";
  if (filter.test(preview)) {
    interestingHandles[key] = now + config.keepHandleMs;
    return true;
  }
  if (interestingHandles[key] && interestingHandles[key] > now) {
    return true;
  }
  return captureAll;
}

function sendChunk(direction, moduleName, symbolName, handle, ptrValue, lenValue) {
  const len = Number(lenValue);
  if (!ptrValue || ptrValue.isNull() || !Number.isFinite(len) || len <= 0) return;
  const captured = Math.min(len, maxBytes);
  const preview = bytesToPreview(ptrValue, captured);
  if (!shouldCapture(handle, preview)) return;
  let data;
  try {
    data = Memory.readByteArray(ptrValue, captured);
  } catch (e) {
    send({type: "read-error", error: String(e), module: moduleName, symbol: symbolName, direction: direction, len: len});
    return;
  }
  send({
    type: "chunk",
    direction: direction,
    module: moduleName,
    symbol: symbolName,
    handle: handle ? handle.toString() : "",
    len: len,
    captured: captured,
    tid: Process.getCurrentThreadId(),
    timestamp: new Date().toISOString(),
    preview: preview.slice(0, 600)
  }, data);
}

function hookAddress(address, label, opts) {
  const key = address.toString() + ":" + label;
  if (hooked[key]) return false;
  hooked[key] = true;
  try {
    Interceptor.attach(address, opts);
    send({type: "hooked", label: label, address: address.toString()});
    return true;
  } catch (e) {
    send({type: "hook-error", label: label, address: address.toString(), error: String(e)});
    return false;
  }
}

function hookWrite(address, moduleName, symbolName, handleArg, bufArg, lenArg) {
  hookAddress(address, moduleName + "!" + symbolName, {
    onEnter(args) {
      sendChunk("out", moduleName, symbolName, args[handleArg], args[bufArg], args[lenArg].toInt32());
    }
  });
}

function hookRead(address, moduleName, symbolName, handleArg, bufArg, lenArg) {
  hookAddress(address, moduleName + "!" + symbolName, {
    onEnter(args) {
      this.handle = args[handleArg];
      this.buf = args[bufArg];
      this.want = args[lenArg].toInt32();
    },
    onLeave(retval) {
      const n = retval.toInt32();
      if (n > 0) sendChunk("in", moduleName, symbolName, this.handle, this.buf, n);
    }
  });
}

function hookWriteEx(address, moduleName, symbolName) {
  hookAddress(address, moduleName + "!" + symbolName, {
    onEnter(args) {
      this.handle = args[0];
      this.buf = args[1];
      this.len = args[2].toUInt32();
      this.writtenPtr = args[3];
    },
    onLeave(retval) {
      let n = this.len;
      try {
        if (retval.toInt32() === 1 && this.writtenPtr && !this.writtenPtr.isNull()) {
          n = Number(this.writtenPtr.readU64());
        }
      } catch (e) {}
      if (n > 0) sendChunk("out", moduleName, symbolName, this.handle, this.buf, n);
    }
  });
}

function hookReadEx(address, moduleName, symbolName) {
  hookAddress(address, moduleName + "!" + symbolName, {
    onEnter(args) {
      this.handle = args[0];
      this.buf = args[1];
      this.len = args[2].toUInt32();
      this.readPtr = args[3];
    },
    onLeave(retval) {
      if (retval.toInt32() !== 1) return;
      let n = 0;
      try {
        if (this.readPtr && !this.readPtr.isNull()) n = Number(this.readPtr.readU64());
      } catch (e) {}
      if (n > 0) sendChunk("in", moduleName, symbolName, this.handle, this.buf, n);
    }
  });
}

function hookExports(module) {
  let exports = [];
  try {
    exports = module.enumerateExports();
  } catch (e) {
    return;
  }
  for (const exp of exports) {
    if (exp.type !== "function" || !moduleContains(module, exp.address)) continue;
    if (exp.name === "SSL_write" || exp.name === "BIO_write") {
      hookWrite(exp.address, module.name, exp.name, 0, 1, 2);
    } else if (exp.name === "SSL_read" || exp.name === "BIO_read") {
      hookRead(exp.address, module.name, exp.name, 0, 1, 2);
    } else if (exp.name === "SSL_write_ex") {
      hookWriteEx(exp.address, module.name, exp.name);
    } else if (exp.name === "SSL_read_ex") {
      hookReadEx(exp.address, module.name, exp.name);
    }
  }
}

function hookSymbols(module) {
  if (!/(ssl|crypto|cronet|conscrypt|flutter|javacrypto)/i.test(module.name)) return;
  let symbols = [];
  try {
    symbols = module.enumerateSymbols();
  } catch (e) {
    return;
  }
  for (const sym of symbols) {
    if (sym.type !== "function") continue;
    if (sym.name === "_ZL9ssl_writeP6bio_stPKci" || sym.name.indexOf("NativeCrypto_ENGINE_SSL_write_direct") >= 0) {
      hookWrite(sym.address, module.name, sym.name, sym.name.indexOf("NativeCrypto_") >= 0 ? 2 : 0, sym.name.indexOf("NativeCrypto_") >= 0 ? 4 : 1, sym.name.indexOf("NativeCrypto_") >= 0 ? 5 : 2);
    } else if (sym.name === "_ZL8ssl_readP6bio_stPci" || sym.name.indexOf("NativeCrypto_ENGINE_SSL_read_direct") >= 0) {
      hookRead(sym.address, module.name, sym.name, sym.name.indexOf("NativeCrypto_") >= 0 ? 2 : 0, sym.name.indexOf("NativeCrypto_") >= 0 ? 4 : 1, sym.name.indexOf("NativeCrypto_") >= 0 ? 5 : 2);
    }
  }
}

function hookLoadedModules() {
  let count = 0;
  for (const module of Process.enumerateModules()) {
    hookExports(module);
    hookSymbols(module);
    count++;
  }
  send({type: "ready", modules: count});
}

hookLoadedModules();
"""


def build_script(args):
    config = {
        "maxBytes": args.max_bytes,
        "captureAll": args.capture_all,
        "filter": args.filter,
        "keepHandleMs": args.keep_handle_ms,
    }
    return FRIDA_SCRIPT.replace("%CONFIG_JSON%", json.dumps(config).replace("\\", "\\\\").replace("'", "\\'"))


def main():
    parser = argparse.ArgumentParser(description="Capture plaintext-ish TLS chunks from one Android app process via Frida.")
    parser.add_argument("--serial", default=os.environ.get("ADB_SERIAL") or "emulator-5554")
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--activity", default=DEFAULT_ACTIVITY)
    parser.add_argument("--launch", action="store_true", help="Launch app if it is not already running.")
    parser.add_argument("--outdir", default="")
    parser.add_argument("--duration", type=int, default=0, help="Seconds to run. 0 means until Ctrl-C.")
    parser.add_argument("--max-bytes", type=int, default=262144)
    parser.add_argument("--filter", default=DEFAULT_FILTER)
    parser.add_argument("--keep-handle-ms", type=int, default=30000)
    parser.add_argument("--capture-all", action="store_true", help="Capture every hooked chunk. Can be noisy.")
    args = parser.parse_args()

    outdir = args.outdir or os.path.join(
        os.getcwd(),
        "runtime",
        "captures",
        f"frida-tls-{safe_slug(args.package)}-{now_label()}",
    )
    os.makedirs(outdir, exist_ok=True)
    chunks_dir = os.path.join(outdir, "chunks")
    os.makedirs(chunks_dir, exist_ok=True)

    pid = resolve_pid(args.serial, args.package, activity=args.activity, launch=args.launch)
    metadata_path = os.path.join(outdir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as fp:
        json.dump(
            {
                "started_at": now_iso(),
                "serial": args.serial,
                "package": args.package,
                "pid": pid,
                "filter": args.filter,
                "capture_all": args.capture_all,
            },
            fp,
            ensure_ascii=False,
            indent=2,
        )

    events_path = os.path.join(outdir, "tls-events.jsonl")
    text_path = os.path.join(outdir, "tls-events.txt")
    hooked_path = os.path.join(outdir, "hooked-functions.txt")
    last_dir_path = os.path.join(os.getcwd(), "runtime", "last-frida-tls-capture-dir.txt")
    os.makedirs(os.path.dirname(last_dir_path), exist_ok=True)
    with open(last_dir_path, "w", encoding="utf-8") as fp:
        fp.write(outdir + "\n")

    state = {"count": 0, "stop": False}

    def write_event(payload, data):
        if payload.get("type") == "hooked":
            with open(hooked_path, "a", encoding="utf-8") as fp:
                fp.write(f"{now_iso()}\t{payload['address']}\t{payload['label']}\n")
            print(f"hooked {payload['label']} @ {payload['address']}", flush=True)
            return
        if payload.get("type") in {"ready", "hook-error", "read-error"}:
            with open(hooked_path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps({"time": now_iso(), **payload}, ensure_ascii=False) + "\n")
            print(json.dumps(payload, ensure_ascii=False), flush=True)
            return
        if payload.get("type") != "chunk":
            print(json.dumps(payload, ensure_ascii=False), flush=True)
            return

        raw = bytes(data or b"")
        if not raw:
            return
        state["count"] += 1
        idx = state["count"]
        label = safe_slug(f"{idx:06d}_{payload.get('direction')}_{payload.get('module')}_{payload.get('symbol')}", 120)
        raw_name = f"{label}.bin"
        txt_name = f"{label}.txt"
        raw_path = os.path.join(chunks_dir, raw_name)
        txt_file_path = os.path.join(chunks_dir, txt_name)
        with open(raw_path, "wb") as fp:
            fp.write(raw)
        text = to_text(raw)
        if is_mostly_text(raw):
            with open(txt_file_path, "w", encoding="utf-8", errors="replace") as fp:
                fp.write(text)
        else:
            txt_name = ""

        record = {
            "index": idx,
            "received_at": now_iso(),
            **payload,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "raw_file": os.path.join("chunks", raw_name),
            "text_file": os.path.join("chunks", txt_name) if txt_name else "",
        }
        record.pop("preview", None)
        with open(events_path, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")
        with open(text_path, "a", encoding="utf-8", errors="replace") as fp:
            fp.write("\n" + "=" * 96 + "\n")
            fp.write(
                f"#{idx} {record['received_at']} {payload.get('direction')} "
                f"{payload.get('module')}!{payload.get('symbol')} "
                f"len={payload.get('len')} captured={payload.get('captured')} handle={payload.get('handle')}\n"
            )
            fp.write("-" * 96 + "\n")
            fp.write(text[: args.max_bytes])
            if not text.endswith("\n"):
                fp.write("\n")
        preview = payload.get("preview", "").replace("\n", "\\n")
        print(f"chunk #{idx} {payload.get('direction')} {payload.get('module')}!{payload.get('symbol')} len={payload.get('len')} {preview[:180]}", flush=True)

    def on_message(message, data):
        if message.get("type") == "send":
            write_event(message.get("payload") or {}, data)
        else:
            print(json.dumps(message, ensure_ascii=False), flush=True)

    def stop_handler(_signum, _frame):
        state["stop"] = True

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    print(f"attaching pid={pid} package={args.package}", flush=True)
    print(f"outdir={outdir}", flush=True)
    device = frida.get_usb_device(timeout=10)
    session = device.attach(pid)
    script = session.create_script(build_script(args))
    script.on("message", on_message)
    script.load()

    started = time.time()
    try:
        while not state["stop"]:
            if args.duration and time.time() - started >= args.duration:
                break
            time.sleep(0.25)
    finally:
        try:
            session.detach()
        except Exception:
            pass
        with open(metadata_path, "r+", encoding="utf-8") as fp:
            meta = json.load(fp)
            meta["finished_at"] = now_iso()
            meta["chunks"] = state["count"]
            fp.seek(0)
            json.dump(meta, fp, ensure_ascii=False, indent=2)
            fp.truncate()
        print(f"capture stopped, chunks={state['count']}, outdir={outdir}", flush=True)


if __name__ == "__main__":
    main()

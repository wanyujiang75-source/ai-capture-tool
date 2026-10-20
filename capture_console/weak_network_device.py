"""Android netem adapter. Never modifies host networking or Android proxy settings."""

import re
import shlex
import uuid


class EmulatorNetworkDevice:
    def __init__(self, runner):
        self.runner = runner
        self.root_prefix = None

    def adb(self, args):
        result = self.runner.adb(args, timeout=8)
        if not result.ok:
            raise RuntimeError(result.text[:2000] or "设备网络命令失败，请打开运行检查。")
        return result.stdout.strip()

    def root(self, command):
        if self.root_prefix is None:
            for prefix in ("", "/debug_ramdisk/magisk su -c ", "su -c "):
                try:
                    value = self.adb(["shell", prefix + shlex.quote("id -u") if prefix else "id -u"])
                    if value == "0":
                        self.root_prefix = prefix
                        break
                except RuntimeError:
                    pass
            if self.root_prefix is None:
                raise RuntimeError("弱网模拟需要已完成环境准备的 Root 模拟器。")
        return self.adb(["shell", self.root_prefix + shlex.quote(command) if self.root_prefix else command])

    def identity(self):
        serial = self.runner.adb_serial
        if not re.fullmatch(r"emulator-[0-9]+", serial):
            raise RuntimeError("弱网模拟暂不支持 Android 真机。")
        avd = self.adb(["emu", "avd", "name"]).splitlines()[0]
        if avd != self.runner.avd_name:
            raise RuntimeError("模拟器与所选设备不一致，请刷新设备后重试。")
        boot = self.adb(["shell", "cat", "/proc/sys/kernel/random/boot_id"])
        if not re.fullmatch(r"[a-f0-9-]{36}", boot):
            raise RuntimeError("无法确认模拟器启动标识。")
        return {"serial": serial, "avd": avd, "boot_id": boot}

    def target(self):
        return {"serial": self.runner.adb_serial, "avd": self.runner.avd_name}

    def snapshot(self):
        saved = self.identity()
        if self.adb(["shell", "getprop", "sys.boot_completed"]) != "1":
            raise RuntimeError("Android 系统仍在启动，请稍后重试。")
        qdiscs = self.root("tc qdisc show")
        interfaces = []
        token = "aiwn" + uuid.uuid4().hex[:8]
        for name in ("wlan0", "eth0"):
            roots = [line for line in qdiscs.splitlines() if f" dev {name} " in line and " root " in line]
            if not roots:
                continue
            if len(roots) != 1 or not re.match(r"qdisc (noqueue|pfifo_fast) 0: ", roots[0]):
                raise RuntimeError(f"{name} 已有其他网络规则，工具不会覆盖。")
            if self.root(f"tc filter show dev {name} ingress"):
                raise RuntimeError(f"{name} 已有入站过滤规则，工具不会覆盖。")
            ifb = f"{token}{len(interfaces)}"
            if self.root(f"ip -o link show | grep -E '^[0-9]+: {ifb}[:@]' || true"):
                raise RuntimeError(f"{ifb} 已存在，请先恢复上次弱网设置。")
            clsact = f" dev {name} " in "\n".join(line for line in qdiscs.splitlines() if " clsact " in line)
            interfaces.append({"name": name, "ifb": ifb, "had_clsact": clsact})
        if not interfaces:
            raise RuntimeError("当前模拟器没有支持的网络接口。")
        saved.update(interfaces=interfaces, token=token)
        return saved

    def same_boot(self, saved):
        token = saved.get("token", "")
        if not re.fullmatch(r"aiwn[a-f0-9]{8}", token):
            raise RuntimeError("弱网恢复记录损坏，未修改设备。")
        if not 1 <= len(saved.get("interfaces", [])) <= 2:
            raise RuntimeError("弱网恢复记录缺少接口，未修改设备。")
        for item in saved["interfaces"]:
            if item.get("name") not in {"wlan0", "eth0"} or item.get("ifb") not in {token + "0", token + "1"}:
                raise RuntimeError("弱网恢复记录包含未知接口，未修改设备。")
        current = self.identity()
        if any(current[key] != saved[key] for key in ("serial", "avd")):
            raise RuntimeError("设备身份已变化，未修改其他模拟器。")
        return current["boot_id"] == saved["boot_id"]

    def apply(self, saved, profile):
        if not self.same_boot(saved):
            raise RuntimeError("模拟器已重新启动，请重试。")
        delay = profile.latency_ms / 2
        commands = ["set -e"]
        for item in saved["interfaces"]:
            name, ifb = item["name"], item["ifb"]
            commands.extend([
                f"ip link add {ifb} type ifb",
                f"ip link set dev {ifb} alias prepared:{saved['token']}",
                f"ip link set dev {ifb} up",
                f"tc qdisc add dev {ifb} root handle 9c11: netem limit 1000 delay {delay:g}ms rate {profile.download_kbps}kbit",
                f"tc qdisc add dev {name} root handle 9c01: netem limit 1000 delay {delay:g}ms rate {profile.upload_kbps}kbit",
                f"ip link set dev {ifb} alias root:{saved['token']}",
            ])
            if not item["had_clsact"]:
                commands.append(f"tc qdisc add dev {name} clsact")
                commands.append(f"ip link set dev {ifb} alias root-clsact:{saved['token']}")
            commands.append(f"tc filter add dev {name} ingress pref 49152 handle 1 matchall action mirred egress redirect dev {ifb}")
        self.root("\n".join(commands))

    def verify(self, saved, profile):
        if not self.same_boot(saved):
            raise RuntimeError("模拟器已重启，弱网规则已失效。")
        qdiscs = self.root("tc qdisc show")
        for item in saved["interfaces"]:
            for interface, handle, rate in (
                (item["name"], "9c01:", profile.upload_kbps),
                (item["ifb"], "9c11:", profile.download_kbps),
            ):
                line = next((line for line in qdiscs.splitlines() if f"qdisc netem {handle} dev {interface} root " in line), "")
                if not line:
                    raise RuntimeError(f"弱网规则缺失：{interface}")
                speed = re.search(r"rate ([0-9.]+)([KMGT]?)bit", line)
                multiplier = {"": 1, "K": 1000, "M": 1000000, "G": 1000000000, "T": 1000000000000}
                if not speed or abs(float(speed[1]) * multiplier[speed[2]] - rate * 1000) > 1000:
                    raise RuntimeError(f"弱网速率校验失败：{interface}")
                latency = re.search(r"delay ([0-9.]+)(us|ms|s)", line)
                actual = float(latency[1]) * {"us": 0.001, "ms": 1, "s": 1000}[latency[2]] if latency else 0
                if abs(actual - profile.latency_ms / 2) > 0.1:
                    raise RuntimeError(f"弱网延迟校验失败：{interface}")
            filters = self.root(f"tc filter show dev {item['name']} ingress")
            if "pref 49152" not in filters or item["ifb"] not in filters:
                raise RuntimeError("下行限速规则未生效。")

    def restore(self, saved):
        if not self.same_boot(saved):
            return  # These kernel objects cannot survive a device reboot.
        commands = ["set -e"]
        for item in saved["interfaces"]:
            name, ifb = item["name"], item["ifb"]
            commands.extend([
                f'owner="$(cat /sys/class/net/{ifb}/ifalias 2>/dev/null || true)"',
                f"filters=\"$(tc filter show dev {name} ingress)\"",
                'if printf "%s" "$filters" | grep -q "pref 49152"; then',
                f'  printf "%s" "$filters" | grep -q "{ifb}" || exit 21',
                f"  tc filter del dev {name} ingress pref 49152 handle 1 matchall",
                "fi",
                'qdiscs="$(tc qdisc show)"',
                f"if printf '%s' \"$qdiscs\" | grep -q 'qdisc netem 9c01: dev {name} root '; then",
                # Mark ownership only after exclusive creation succeeds. Ambiguous crashes fail closed.
                f'  [ "$owner" = "root:{saved["token"]}" ] || [ "$owner" = "root-clsact:{saved["token"]}" ] || exit 24',
                f"  tc qdisc del dev {name} root handle 9c01:",
                "fi",
            ])
            if not item["had_clsact"]:
                commands.extend([
                    f'if [ "$owner" = "root-clsact:{saved["token"]}" ] && printf \'%s\' "$qdiscs" | grep -q \'qdisc clsact ffff: dev {name} \'; then',
                    f'  if [ -z "$(tc filter show dev {name} ingress)" ] && [ -z "$(tc filter show dev {name} egress)" ]; then',
                    f"    tc qdisc del dev {name} clsact",
                    "  fi",
                    "fi",
                ])
            commands.extend([
                # Keep the alias until all other cleanup succeeds so a retry retains ownership.
                f"if [ -d /sys/class/net/{ifb} ]; then",
                f'  case "$owner" in prepared:{saved["token"]}|root:{saved["token"]}|root-clsact:{saved["token"]}) ;; *) exit 25;; esac',
                f"  ip link del dev {ifb}",
                "fi",
                'qdiscs="$(tc qdisc show)"',
                f"if printf '%s' \"$qdiscs\" | grep -q 'qdisc netem 9c01: dev {name} root '; then exit 22; fi",
                f"if [ -d /sys/class/net/{ifb} ]; then exit 23; fi",
            ])
        self.root("\n".join(commands))

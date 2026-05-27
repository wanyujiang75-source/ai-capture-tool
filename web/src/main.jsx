import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  actionMessageAutoDismissMs,
  formatActionError,
  formatActionPending,
  formatActionSuccess,
} from "./actionMessage.js";
import { appEnvironmentLabel, groupAppsByEnvironment } from "./appEnvironment.js";
import { deviceState, releaseActionHint, releaseActionLabel, residentSummary } from "./deviceUi.js";
import { applyFlowClearMarker, createFlowClearMarker } from "./flowClear.js";
import { matchesMethod, methodFilterOptions } from "./flowMethods.js";
import { compactTimestamp, flowTimingInfo, flowTimingRows, flowTimingSummary } from "./flowTiming.js";
import { networkModeLabel, preflightSummary } from "./networkDiagnostics.js";
import { scheduleDelayedReadinessRefresh } from "./readinessRefresh.js";
import { setupCurrentStep, setupDeviceSummary, shouldShowSetupWizard } from "./setupWizard.js";
import { buildUploadInstallPath } from "./uploadPackage.js";
import "./styles.css";

const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { "content-type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
    const error = new Error(message);
    error.payload = payload;
    error.status = response.status;
    throw error;
  }
  return payload;
};

const emptyApp = {
  platform: "android",
  environment: "production",
  name: "MelodyCraft",
  package_name: "",
  activity: "",
  default_mode: "flutter-socks",
  notes: "保留登录态模拟器上的应用",
};

const STATIC_EXTENSIONS = [
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".webp",
  ".svg",
  ".ico",
  ".mp3",
  ".mp4",
  ".m4a",
  ".aac",
  ".wav",
  ".css",
  ".js",
  ".woff",
  ".woff2",
  ".ttf",
  ".otf",
];

const NOISE_HOST_HINTS = [
  "doubleclick",
  "googleads",
  "googlesyndication",
  "applovin",
  "unityads",
  "vungle",
  "adjust",
  "firebase",
  "crashlytics",
  "analytics",
  "sentry",
  "datadog",
  "intercom",
  "connectivitycheck",
  "gstatic",
];

const FLOW_DETAIL_FILTERS = [
  { value: "all", label: "不限" },
  { value: "categoryBusiness", label: "业务 API" },
  { value: "categoryOther", label: "其他接口" },
  { value: "categoryNoise", label: "噪声/素材" },
  { value: "highScore", label: "高分接口" },
  { value: "status200", label: "HTTP 200" },
  { value: "noResponse", label: "NO_RESPONSE" },
  { value: "hasRequest", label: "有 Request Body" },
  { value: "hasResponse", label: "有 Response Body" },
];

function flowPath(flow) {
  return flow.path || flow.url || "/";
}

function isStaticAsset(flow) {
  const target = `${flowPath(flow)} ${flow.url || ""}`.toLowerCase().split("?")[0];
  return STATIC_EXTENSIONS.some((extension) => target.includes(extension));
}

function isNoise(flow) {
  const host = (flow.host || "").toLowerCase();
  return NOISE_HOST_HINTS.some((hint) => host.includes(hint));
}

function flowCategory(flow) {
  if (isStaticAsset(flow)) return "asset";
  if (isNoise(flow)) return "noise";
  if ((flow.score || 0) >= 80) return "business";
  if (["POST", "PUT", "PATCH", "DELETE"].includes((flow.method || "").toUpperCase())) return "business";
  return "other";
}

function formatJson(value) {
  if (value === null || value === undefined || value === "") return "无";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function compactFlowTime(value) {
  return compactTimestamp(value);
}

function appVersionLabel(app) {
  if (!app?.version_name && !app?.version_code) return "版本未同步";
  const code = app.version_code ? `(${app.version_code})` : "";
  return `${app.version_name || "unknown"} ${code}`.trim();
}

function validationLabel(status) {
  return {
    passed: "抓包可用",
    warning: "需要确认",
    failed: "校验失败",
  }[status] || "未校验";
}

function googleStateLabel(state) {
  return {
    ok: "Google 已登录",
    not_logged_in: "未登录 Google",
    missing_play_store: "缺少 Google Play",
    adb_unavailable: "无法检查 Google",
  }[state?.state] || "无法检查 Google";
}

function googleStateClass(state) {
  if (state?.state === "ok") return "ok";
  if (state?.state === "not_logged_in") return "warn";
  return "fail";
}

function enrichFlow(flow) {
  const category = flowCategory(flow);
  return { ...flow, category };
}

function matchesFlowFilter(flow, filter) {
  const hostNeedle = filter.host.trim().toLowerCase();
  const pathNeedle = filter.path.trim().toLowerCase();
  if (hostNeedle && !(flow.host || "").toLowerCase().includes(hostNeedle)) return false;
  if (pathNeedle && !`${flowPath(flow)} ${flow.url || ""}`.toLowerCase().includes(pathNeedle)) return false;
  if (!matchesMethod(flow, filter.method || "all")) return false;

  switch (filter.detail || "all") {
    case "categoryBusiness":
      return flow.category === "business";
    case "categoryOther":
      return flow.category === "other";
    case "categoryNoise":
      return ["noise", "asset"].includes(flow.category);
    case "highScore":
      return (flow.score || 0) >= 80;
    case "status200":
      return String(flow.status) === "200";
    case "noResponse":
      return String(flow.status) === "NO_RESPONSE";
    case "hasRequest":
      return Boolean(flow.has_request_json || flow.request_bin);
    case "hasResponse":
      return String(flow.status) !== "NO_RESPONSE" && Boolean(flow.has_response_json || flow.response_bin);
    default:
      return true;
  }
}

function App() {
  const [status, setStatus] = useState(null);
  const [devices, setDevices] = useState([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState("device-1");
  const [apps, setApps] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [sessionView, setSessionView] = useState("live");
  const [flows, setFlows] = useState([]);
  const [flowDetails, setFlowDetails] = useState({});
  const [flowCurls, setFlowCurls] = useState({});
  const [expandedFlows, setExpandedFlows] = useState({});
  const [flowTabs, setFlowTabs] = useState({});
  const [flowClearMarkers, setFlowClearMarkers] = useState({});
  const [flowFilter, setFlowFilter] = useState({ method: "all", detail: "all", host: "", path: "" });
  const [form, setForm] = useState(emptyApp);
  const [selectedAppId, setSelectedAppId] = useState("");
  const [readiness, setReadiness] = useState(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [setup, setSetup] = useState(null);
  const [setupForcedOpen, setSetupForcedOpen] = useState(false);
  const [diagnostics, setDiagnostics] = useState(null);

  const loadAll = async () => {
    const [nextStatus, deviceData, appData, captureData] = await Promise.all([
      api("/api/status"),
      api("/api/devices"),
      api("/api/apps"),
      api("/api/captures"),
    ]);
    setStatus(nextStatus);
    const nextDevices = deviceData.devices || [];
    setDevices(nextDevices);
    setSelectedDeviceId((previous) => {
      if (previous && nextDevices.some((item) => item.device_id === previous)) {
        return previous;
      }
      return nextDevices[0]?.device_id || "device-1";
    });
    const nextApps = appData.apps || [];
    setApps(nextApps);
    setSelectedAppId((previous) => {
      if (previous && nextApps.some((item) => String(item.id) === String(previous))) {
        return previous;
      }
      const firstAndroid = nextApps.find((item) => item.platform === "android") || nextApps[0];
      return firstAndroid ? String(firstAndroid.id) : "";
    });
    setSessions(captureData.sessions || []);
  };

  const loadSetupState = async () => {
    const data = await api("/api/setup/state");
    setSetup(data.setup);
    return data.setup;
  };

  const selectedApp = apps.find((item) => String(item.id) === String(selectedAppId));
  const selectedDevice = devices.find((item) => item.device_id === selectedDeviceId) || devices[0];
  const selectedDeviceCapture = selectedDevice?.capture || status || {};
  const selectedDeviceActiveSession = selectedDevice?.active_session || null;
  const selectedAppCanCapture = Boolean(selectedApp) && (selectedApp?.platform || "android") === "android";
  const selectedDeviceReady = Boolean(selectedDevice?.emulator?.adb_online && selectedDevice?.emulator?.boot_completed);
  const selectedGoogleState = selectedDevice?.google_state || {};
  const selectedGoogleReady = Boolean(selectedGoogleState.ok);
  const mitmWebUrl = selectedDevice ? `http://127.0.0.1:${selectedDevice.web_port}/?token=android-capture` : "http://127.0.0.1:9091/?token=android-capture";

  const loadReadiness = async (appId = selectedAppId) => {
    if (!appId) {
      setReadiness(null);
      return null;
    }
    setReadinessLoading(true);
    try {
      const data = await api(`/api/apps/${appId}/readiness?device_id=${encodeURIComponent(selectedDeviceId)}`);
      setReadiness(data.readiness);
      return data.readiness;
    } finally {
      setReadinessLoading(false);
    }
  };

  useEffect(() => {
    loadAll().catch((error) => setMessage(formatActionError("加载状态", error)));
    loadSetupState().catch(() => {});
    const timer = setInterval(() => loadAll().catch(() => {}), 5000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!selectedAppId) {
      setReadiness(null);
      return undefined;
    }

    const refresh = () =>
      loadReadiness(selectedAppId).catch((error) => {
        setReadiness({
          state: "fail",
          checks: [
            {
              name: "readiness_api",
              label: "校验服务",
              state: "fail",
              summary: "校验状态读取失败。",
              detail: error.message,
            },
          ],
        });
      });
    refresh();
    const timer = setInterval(refresh, 12000);
    return () => clearInterval(timer);
  }, [selectedAppId, selectedDeviceId]);

  const runAction = async (label, action) => {
    setLoading(true);
    setMessage(formatActionPending(label));
    try {
      await action();
      await loadAll();
      await loadSetupState().catch(() => {});
      if (selectedAppId) {
        await loadReadiness(selectedAppId).catch(() => {});
      }
      setMessage(formatActionSuccess(label));
    } catch (error) {
      setMessage(formatActionError(label, error));
    } finally {
      setLoading(false);
    }
  };

  const saveApp = () =>
    runAction("保存应用", async () => {
      const result = await api("/api/apps", { method: "POST", body: JSON.stringify(form) });
      setSelectedAppId(String(result.app.id));
      setForm(emptyApp);
    });

  const startCapture = (target, mode) =>
    runAction("启动抓包", async () => {
      if (!target) {
        throw new Error("请先选择应用");
      }
      if ((target.platform || "android") !== "android") {
        throw new Error("当前版本只支持 Android 抓包；iOS 仅预留入口，暂未实现。");
      }
      const result = await api("/api/captures/start", {
        method: "POST",
        body: JSON.stringify({ app_id: target.id, mode, device_id: selectedDeviceId }),
      });
      setSessionView("live");
      setSelectedSession(result.session);
    });

  const stopCapture = () =>
    runAction("停止抓包", async () => {
      await api(`/api/captures/stop?device_id=${encodeURIComponent(selectedDeviceId)}`, { method: "POST" });
    });

  const startEmulator = () =>
    runAction("启动模拟器", async () => {
      const result = await api(`/api/devices/${encodeURIComponent(selectedDeviceId)}/start`, { method: "POST" });
      if (!result.ok) {
        throw new Error(result.stderr || result.stdout || "启动模拟器失败");
      }
    });

  const openEmulatorPreview = () => {
    const previewWindow = window.open("about:blank", "_blank");
    return runAction("打开模拟器画面", async () => {
      try {
        const result = await api(`/api/devices/${encodeURIComponent(selectedDeviceId)}/preview`);
        if (!result.url) {
          throw new Error(result.user_message || "没有可用的模拟器预览入口");
        }
        if (previewWindow) {
          previewWindow.location.href = result.url;
        } else {
          window.open(result.url, "_blank", "noopener,noreferrer");
        }
      } catch (error) {
        if (previewWindow) previewWindow.close();
        throw error;
      }
    });
  };

  const openGoogleLogin = () =>
    runAction("打开 Google 登录", async () => {
      const result = await api(`/api/devices/${encodeURIComponent(selectedDeviceId)}/open-google-login`, { method: "POST" });
      if (!result.ok) {
        throw new Error(result.stderr || result.stdout || "无法打开 Google 登录入口");
      }
    });

  const releaseSelectedDevice = (forceShutdown = false) =>
    runAction(forceShutdown ? "强制关闭设备" : releaseActionLabel(selectedDevice), async () => {
      const suffix = forceShutdown ? "?force_shutdown=true" : "";
      await api(`/api/devices/${encodeURIComponent(selectedDeviceId)}/release${suffix}`, { method: "POST" });
      setSessionView("live");
      setSelectedSession(null);
    });

  const launchSelectedApp = (target) =>
    runAction("打开应用", async () => {
      if (!target) {
        throw new Error("请先选择应用");
      }
      if ((target.platform || "android") !== "android") {
        throw new Error("当前版本只支持启动 Android 应用；iOS 仅预留入口，暂未实现。");
      }
      await api(`/api/apps/${target.id}/launch?device_id=${encodeURIComponent(selectedDeviceId)}`, { method: "POST" });
      scheduleDelayedReadinessRefresh({
        appId: String(target.id),
        refresh: (appId) => loadReadiness(appId).catch(() => {}),
      });
    });

  const syncSelectedVersion = (target) =>
    runAction("同步版本", async () => {
      if (!target) {
        throw new Error("请先选择应用");
      }
      await api(`/api/apps/${target.id}/sync-version?device_id=${encodeURIComponent(selectedDeviceId)}`, { method: "POST" });
    });

  const validateSelectedCapture = (target) =>
    runAction("抓包校验", async () => {
      if (!target) {
        throw new Error("请先选择应用");
      }
      const result = await api(`/api/apps/${target.id}/validate-capture?device_id=${encodeURIComponent(selectedDeviceId)}`, { method: "POST" });
      if (!result.ok) {
        const error = new Error(result.validation?.message || "抓包校验未通过");
        error.payload = result;
        throw error;
      }
    });

  const installPackage = (environment, file) =>
    runAction("安装更新包", async () => {
      if (!file) {
        throw new Error("请选择 APK、APKS 或 ZIP 文件");
      }
      const installResult = await api(buildUploadInstallPath(environment, file.name, selectedDeviceId), {
        method: "POST",
        headers: {
          "content-type": "application/octet-stream",
          "x-filename": file.name,
        },
        body: file,
      });
      if (installResult.app?.id) {
        setSelectedAppId(String(installResult.app.id));
      }
      const validation = await api(`/api/apps/${installResult.app.id}/validate-capture?device_id=${encodeURIComponent(selectedDeviceId)}`, { method: "POST" });
      if (!validation.ok) {
        const error = new Error(validation.validation?.message || "安装完成，但抓包校验未通过");
        error.payload = validation;
        throw error;
      }
    });

  const cleanup = () =>
    runAction("清理脏状态", async () => {
      await api(`/api/cleanup?device_id=${encodeURIComponent(selectedDeviceId)}`, { method: "POST" });
    });

  const checkSetup = () =>
    runAction("环境检查", async () => {
      setSetupForcedOpen(true);
      const data = await api("/api/setup/check", { method: "POST" });
      setSetup(data.setup);
    });

  const checkNetworkDiagnostics = () =>
    runAction("端口与网络检查", async () => {
      const [preflightData, networkData] = await Promise.all([
        api("/api/system/preflight"),
        api(`/api/devices/${encodeURIComponent(selectedDeviceId)}/network-state`),
      ]);
      setDiagnostics({
        preflight: preflightData.preflight,
        network: networkData.network,
      });
    });

  const switchMaintenanceNetwork = () =>
    runAction("切换维护网络", async () => {
      const data = await api(`/api/devices/${encodeURIComponent(selectedDeviceId)}/network/maintenance`, { method: "POST" });
      const preflightData = await api("/api/system/preflight");
      setDiagnostics({ preflight: preflightData.preflight, network: data.network });
    });

  const switchCaptureNetwork = () =>
    runAction("切换抓包网络", async () => {
      const data = await api(`/api/devices/${encodeURIComponent(selectedDeviceId)}/network/capture`, { method: "POST" });
      const preflightData = await api("/api/system/preflight");
      setDiagnostics({ preflight: preflightData.preflight, network: data.network });
    });

  const prepareSelectedFrida = () =>
    runAction("启动 Frida", async () => {
      const result = await api(`/api/devices/${encodeURIComponent(selectedDeviceId)}/prepare-frida`, { method: "POST" });
      if (!result.ok) {
        const error = new Error(result.frida?.detail || result.stderr || "Frida 准入失败");
        error.payload = result;
        throw error;
      }
    });

  const completeSetup = () =>
    runAction("完成初始化", async () => {
      const data = await api("/api/setup/mark-complete", { method: "POST" });
      setSetup(data.setup);
      setSetupForcedOpen(false);
    });

  const sortFlows = (items) =>
    (items || []).map(enrichFlow).slice().sort((a, b) => String(b.time).localeCompare(String(a.time)));

  const refreshFlows = async (session) => {
    if (!session?.id) return;
    const data = await api(`/api/captures/${session.id}/flows`);
    setFlows(sortFlows(data.flows));
  };

  const loadFlows = async (session) => {
    setSessionView("history");
    setSelectedSession(session);
    await refreshFlows(session);
  };

  useEffect(() => {
    const active = selectedDeviceActiveSession;
    if (!active) return;
    setSelectedSession((previous) => {
      if (sessionView === "history" && previous?.id && previous.id !== active.id) {
        return previous;
      }
      return previous?.id === active.id ? { ...previous, ...active } : active;
    });
    if (sessionView !== "history" || selectedSession?.id === active.id) {
      setSessionView("live");
    }
  }, [selectedDeviceActiveSession?.id, selectedDeviceActiveSession?.updated_at, sessionView, selectedSession?.id]);

  useEffect(() => {
    setFlowDetails({});
    setFlowCurls({});
    setExpandedFlows({});
    setFlowTabs({});
    setFlows([]);
  }, [selectedSession?.id]);

  useEffect(() => {
    if (!selectedSession?.id) return undefined;

    let cancelled = false;
      const activeSessionId = selectedDeviceActiveSession?.id;
    const shouldPoll = sessionView === "live" && activeSessionId === selectedSession.id;
    const refresh = async () => {
      try {
        const data = await api(`/api/captures/${selectedSession.id}/flows`);
        if (!cancelled) {
          setFlows(sortFlows(data.flows));
        }
      } catch (error) {
        if (!cancelled) {
          setMessage(formatActionError("刷新接口列表", error));
        }
      }
    };

    refresh();
    const timer = shouldPoll ? window.setInterval(refresh, 2000) : null;
    return () => {
      cancelled = true;
      if (timer) window.clearInterval(timer);
    };
  }, [selectedSession?.id, sessionView, selectedDeviceActiveSession?.id]);

  const loadDetail = async (flow) => {
    if (!selectedSession) return;
    if (flowDetails[flow.id]) return;
    const nextDetail = await api(`/api/captures/${selectedSession.id}/flows/${encodeURIComponent(flow.id)}`);
    const nextCurl = await api(`/api/captures/${selectedSession.id}/flows/${encodeURIComponent(flow.id)}/curl`, {
      headers: { accept: "text/plain" },
    });
    setFlowDetails((previous) => ({ ...previous, [flow.id]: nextDetail }));
    setFlowCurls((previous) => ({ ...previous, [flow.id]: nextCurl }));
  };

  const clearCurrentFlowList = () => {
    if (!selectedSession?.id) return;
    setFlowClearMarkers((previous) => ({
      ...previous,
      [selectedSession.id]: createFlowClearMarker(flows),
    }));
    setFlowDetails({});
    setFlowCurls({});
    setExpandedFlows({});
    setFlowTabs({});
    setMessage(formatActionSuccess("清空接口列表"));
  };

  const selectedFlowClearMarker = selectedSession?.id ? flowClearMarkers[selectedSession.id] : null;
  const visibleFlows = applyFlowClearMarker(flows, selectedFlowClearMarker);
  const flowListCleared = Boolean(selectedFlowClearMarker?.hiddenIds?.length);
  const filteredFlows = visibleFlows.filter((flow) => matchesFlowFilter(flow, flowFilter));
  const emulator = selectedDevice?.emulator || status?.emulator;
  const emulatorReady = Boolean(emulator?.adb_online && emulator?.boot_completed);
  const emulatorUnlocked = Boolean(emulatorReady && emulator?.unlocked);
  const googleReady = Boolean(selectedGoogleReady);
  const selectedMode = selectedApp?.default_mode || selectedDeviceCapture?.mode || "-";
  const captureRunning = selectedDeviceCapture?.health === "running" || Boolean(selectedDeviceActiveSession);
  const selectedSessionIsLive = Boolean(selectedSession?.id && selectedDeviceActiveSession?.id === selectedSession.id && sessionView === "live");
  const recentSessions = sessions.filter((session) => !selectedDeviceId || session.device_id === selectedDeviceId).slice(0, 8);
  const groupedApps = groupAppsByEnvironment(apps);
  const canOperateSelectedApp = selectedAppCanCapture && googleReady;
  const canInstallPackage = selectedAppCanCapture && emulatorUnlocked && googleReady;
  const installDisabledReason = !selectedAppCanCapture
    ? "请先选择 Android 应用。"
    : !emulatorReady
      ? "请先启动模拟器，等待系统启动完成后再上传更新包。"
      : !emulator?.unlocked
        ? "请先解锁模拟器后再上传更新包。"
        : !googleReady
          ? selectedGoogleState.user_message || "请先完成 Google 登录后再上传更新包。"
        : "";
  const residentStatus = residentSummary(devices);
  const showSetupWizard = shouldShowSetupWizard(setup, setupForcedOpen);

  return (
    <main className="console-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">AI</span>
          <div>
            <strong className="brand-name">AI抓包工具</strong>
            <p className="eyebrow">Local Android Packet Capture</p>
          </div>
        </div>
        <div className="topbar-actions">
          <span className={selectedDeviceReady ? "status-chip ok" : "status-chip warn"}>
            {selectedDeviceReady ? "当前设备在线" : "当前设备未就绪"}
          </span>
          <span className="status-chip">系统 {status?.system?.state || "running"}</span>
          <span className={residentStatus.ready ? "status-chip ok" : "status-chip warn"}>{residentStatus.label}</span>
          <span className={`status-chip ${googleStateClass(selectedGoogleState)}`}>{googleStateLabel(selectedGoogleState)}</span>
          <span className="status-chip">Android V1</span>
          <button className="ghost-button" onClick={checkSetup} disabled={loading}>环境检查</button>
          <button className="ghost-button" onClick={() => runAction("刷新状态", loadAll)} disabled={loading}>刷新</button>
          <a className="ghost-button" href={mitmWebUrl} target="_blank" rel="noreferrer">
            mitmweb
          </a>
        </div>
      </header>

      {showSetupWizard ? (
        <SetupWizard
          setup={setup}
          apps={apps}
          selectedDeviceId={selectedDeviceId}
          onSelectDevice={setSelectedDeviceId}
          selectedApp={selectedApp}
          loading={loading}
          onCheck={checkSetup}
          onStartDevice={startEmulator}
          onOpenPreview={openEmulatorPreview}
          onOpenGoogleLogin={openGoogleLogin}
          onPrepareFrida={prepareSelectedFrida}
          onInstall={(environment, file) => installPackage(environment, file)}
          onValidate={() => validateSelectedCapture(selectedApp)}
          onComplete={completeSetup}
          onClose={() => setSetupForcedOpen(false)}
        />
      ) : (
      <section className="workspace">
        <aside className="workflow-rail">
          <div className={emulatorReady ? "workflow-step complete" : "workflow-step active"}>
            <span>01</span>
            <strong>模拟器</strong>
            <small>启动 / 解锁 / 网络</small>
          </div>
          <div className={selectedApp ? "workflow-step complete" : "workflow-step active"}>
            <span>02</span>
            <strong>应用</strong>
            <small>选择或添加目标 App</small>
          </div>
          <div className={status?.health === "running" ? "workflow-step complete" : "workflow-step"}>
            <span>03</span>
            <strong>抓包</strong>
            <small>system / flutter-socks</small>
          </div>
          <div className={selectedSession ? "workflow-step complete" : "workflow-step"}>
            <span>04</span>
            <strong>分析</strong>
            <small>展开查看请求响应</small>
          </div>
          <div className="workflow-step disabled">
            <span>iOS</span>
            <strong>预留入口</strong>
            <small>V1 暂不执行</small>
          </div>
        </aside>

        <div className="primary-column">
          <Panel title="当前任务" eyebrow="Capture Control" className="task-panel">
            <DevicePool
              devices={devices}
              selectedDeviceId={selectedDeviceId}
              onSelect={setSelectedDeviceId}
            />
            <div className="task-grid">
              <div className="metric-card">
                <span>模拟器</span>
                <strong>{selectedDevice?.avd_name || emulator?.current_avd || emulator?.avd_name || "Medium_Phone_API_36.1"}</strong>
                <small>{emulatorReady ? "在线，可用于抓包" : "需要先启动或解锁"}</small>
              </div>
              <div className="metric-card">
                <span>目标应用</span>
                <strong>{selectedApp?.name || "未选择"}</strong>
                <small>{selectedApp?.package_name || "从右侧应用库选择"}</small>
              </div>
              <div className="metric-card">
                <span>抓包模式</span>
                <strong>{selectedMode}</strong>
                <small>{selectedDeviceCapture?.proxy || `proxy ${selectedDevice?.proxy_port || 9090} / web ${selectedDevice?.web_port || 9091}`}</small>
              </div>
            </div>

            <GoogleStatePanel state={selectedGoogleState} loading={loading} onOpenLogin={openGoogleLogin} />

            <div className="current-app-card">
              {selectedApp ? (
                <>
                  <div>
                    <strong>{selectedApp.name}</strong>
                    <code>{selectedApp.package_name}</code>
                    <small>{selectedApp.activity || "启动前自动解析 Activity"}</small>
                    <small>{appEnvironmentLabel(selectedApp.environment)} · {appVersionLabel(selectedApp)} · {validationLabel(selectedApp.last_validation_status)}</small>
                  </div>
                  <span className={selectedAppCanCapture ? "badge" : "badge muted-badge"}>
                    {selectedAppCanCapture ? "Android 可抓包" : "iOS 仅预留入口"}
                  </span>
                </>
              ) : (
                <p className="muted">先在右侧选择应用，或展开“添加应用”保存新的 App。</p>
              )}
            </div>

            <AppVersionPanel
              app={selectedApp}
              loading={loading}
              canCapture={canOperateSelectedApp}
              canInstall={canInstallPackage}
              installDisabledReason={installDisabledReason}
              onSync={() => syncSelectedVersion(selectedApp)}
              onValidate={() => validateSelectedCapture(selectedApp)}
              onInstall={(environment, file) => installPackage(environment, file)}
            />

            <ReadinessPanel readiness={readiness} loading={readinessLoading} />

            <div className="actions primary-actions">
              <button onClick={startEmulator} disabled={loading}>启动模拟器</button>
              <button className="secondary" onClick={openEmulatorPreview} disabled={loading || !selectedDevice}>
                查看模拟器
              </button>
              <button className="secondary" onClick={() => launchSelectedApp(selectedApp)} disabled={loading || !canOperateSelectedApp}>
                打开应用
              </button>
              <button className="secondary" onClick={openGoogleLogin} disabled={loading || googleReady || !selectedDeviceReady}>
                去登录 Google
              </button>
              <button onClick={() => startCapture(selectedApp, selectedApp?.default_mode)} disabled={loading || !canOperateSelectedApp || captureRunning}>
                {captureRunning ? "抓包运行中" : "启动抓包"}
              </button>
              <button className="secondary" onClick={stopCapture} disabled={loading}>停止抓包</button>
              <button
                className="secondary danger-lite"
                onClick={() => releaseSelectedDevice(false)}
                disabled={loading || !selectedDevice}
                title={releaseActionHint(selectedDevice)}
              >
                {releaseActionLabel(selectedDevice)}
              </button>
            </div>

            <details className="advanced-panel">
              <summary>高级 / 排错</summary>
              <NetworkDiagnostics
                diagnostics={diagnostics}
                loading={loading}
                onCheck={checkNetworkDiagnostics}
                onMaintenance={switchMaintenanceNetwork}
                onCapture={switchCaptureNetwork}
              />
              <EmulatorView emulator={emulator} />
              <StatusView status={status} />
              <div className="actions">
                <button className="secondary" onClick={cleanup} disabled={loading}>一键清理脏状态</button>
                <button className="secondary" onClick={() => startCapture(selectedApp, "system")} disabled={loading || !canOperateSelectedApp || captureRunning}>system</button>
                <button className="secondary" onClick={() => startCapture(selectedApp, "flutter-socks")} disabled={loading || !canOperateSelectedApp || captureRunning}>flutter-socks</button>
                <button className="secondary danger-lite" onClick={() => releaseSelectedDevice(true)} disabled={loading || !selectedDevice}>
                  强制关闭设备
                </button>
              </div>
            </details>
          </Panel>

          <Panel
            title={selectedSession ? `接口分析 · ${selectedSessionIsLive ? "实时 " : ""}#${selectedSession.id}` : "接口分析"}
            eyebrow="Flows"
            className="analysis-panel"
            actions={selectedSession ? (
              <button
                className="secondary clear-flow-action"
                onClick={clearCurrentFlowList}
                disabled={!visibleFlows.length}
                title="只清空当前页面列表，不停止抓包、不删除原始文件。"
              >
                清空当前列表
              </button>
            ) : null}
          >
            {selectedSession ? (
              <FlowAnalysis
                flows={visibleFlows}
                filteredFlows={filteredFlows}
                sourceFlowCount={flows.length}
                isCleared={flowListCleared}
                filter={flowFilter}
                onFilterChange={setFlowFilter}
                details={flowDetails}
                curls={flowCurls}
                expandedFlows={expandedFlows}
                flowTabs={flowTabs}
                onToggleFlow={(flow, isOpen) => setExpandedFlows((previous) => ({ ...previous, [flow.id]: isOpen }))}
                onChangeFlowTab={(flowId, tab) => setFlowTabs((previous) => ({ ...previous, [flowId]: tab }))}
                onLoadDetail={(flow) => loadDetail(flow).catch((error) => setMessage(formatActionError("加载接口详情", error)))}
              />
            ) : (
              <div className="empty-state">
                <strong>启动抓包后会自动进入实时分析</strong>
                <p>操作 App 时接口列表会自动刷新；右侧历史任务只作为记录入口，用于回看某一次 session。</p>
              </div>
            )}
          </Panel>
        </div>

        <aside className="side-column">
          <Panel title="应用库" eyebrow="Apps" className="side-panel">
            <label className="app-picker">
              当前应用
              <select value={selectedAppId} onChange={(event) => setSelectedAppId(event.target.value)}>
                <option value="">请选择应用</option>
                {groupedApps.production.length ? (
                  <optgroup label="生产包">
                    {groupedApps.production.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} · {item.package_name}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
                {groupedApps.test.length ? (
                  <optgroup label="测试包">
                    {groupedApps.test.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} · {item.package_name}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
              </select>
            </label>
            <AppGroupList groupedApps={groupedApps} selectedAppId={selectedAppId} onSelect={setSelectedAppId} />
            {apps.length === 0 && <p className="muted compact-hint">还没有应用条目。</p>}

            <details className="drawer">
              <summary>添加应用</summary>
              <div className="form">
                <label>
                  平台
                  <select value={form.platform} onChange={(event) => setForm({ ...form, platform: event.target.value })}>
                    <option value="android">Android</option>
                    <option value="ios">iOS（预留入口，暂不可抓包）</option>
                  </select>
                </label>
                <label>
                  包类型
                  <select value={form.environment} onChange={(event) => setForm({ ...form, environment: event.target.value })}>
                    <option value="production">生产包</option>
                    <option value="test">测试包</option>
                  </select>
                </label>
                <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="应用名" />
                <input value={form.package_name} onChange={(event) => setForm({ ...form, package_name: event.target.value })} placeholder="包名，例如 com.xxx.app" />
                <input value={form.activity} onChange={(event) => setForm({ ...form, activity: event.target.value })} placeholder="Activity，可留空自动解析" />
                <select value={form.default_mode} onChange={(event) => setForm({ ...form, default_mode: event.target.value })}>
                  <option value="system">system</option>
                  <option value="flutter-socks">flutter-socks</option>
                </select>
                <textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} placeholder="备注" />
                <button onClick={saveApp} disabled={loading || !form.name || !form.package_name}>保存应用</button>
              </div>
            </details>
          </Panel>

          <Panel title="历史任务" eyebrow="Sessions" className="side-panel">
            <div className="history">
              {recentSessions.map((session) => (
                <button
                  className={selectedSession?.id === session.id ? "session selected" : "session"}
                  key={session.id}
	                  onClick={() => loadFlows(session).catch((error) => setMessage(formatActionError("加载历史任务", error)))}
	                >
	                  <span className="session-id">{session.adb_serial || `#${session.id}`}</span>
	                  <strong>{session.app_name || "历史目录"}</strong>
	                </button>
              ))}
              {recentSessions.length === 0 && <p className="muted">暂无历史任务。</p>}
            </div>
          </Panel>
        </aside>
      </section>
      )}

      {message && <ActionToast message={message} onClose={() => setMessage(null)} />}
    </main>
  );
}

function SetupWizard({
  setup,
  apps,
  selectedDeviceId,
  onSelectDevice,
  selectedApp,
  loading,
  onCheck,
  onStartDevice,
  onOpenPreview,
  onOpenGoogleLogin,
  onPrepareFrida,
  onInstall,
  onValidate,
  onComplete,
  onClose,
}) {
  const current = setupCurrentStep(setup);
  const summary = setupDeviceSummary(setup?.devices || []);
  const selectedDevice = (setup?.devices || []).find((device) => device.device_id === selectedDeviceId) || setup?.devices?.[0];
  const envChecks = setup?.env?.checks || [];
  const steps = setup?.steps || [];
  const hasApp = apps.length > 0;
  const selectedEmulatorReady = Boolean(
    selectedDevice?.emulator?.adb_online &&
    selectedDevice?.emulator?.boot_completed &&
    selectedDevice?.emulator?.unlocked
  );
  const selectedEmulatorMessage = !selectedDevice?.emulator?.adb_online
    ? "未启动"
    : !selectedDevice?.emulator?.boot_completed
      ? "等待 Android 启动完成"
      : !selectedDevice?.emulator?.unlocked
        ? "需要手动解锁"
        : "设备在线并已解锁";

  return (
    <section className="setup-shell">
      <Panel
        title="AI抓包工具初始化"
        eyebrow="Setup"
        className="setup-panel"
        actions={setup?.completed ? (
          <button className="secondary" onClick={onClose}>进入控制台</button>
        ) : null}
      >
        <div className="setup-hero">
          <div>
            <strong>{setup?.completed ? "初始化已完成" : "当前状态：服务已启动，设备尚未完成准入"}</strong>
            <p>{current.label}：{current.description}</p>
          </div>
          <span className={summary.ok ? "status-chip ok" : "status-chip warn"}>{summary.label}</span>
        </div>

        <div className="setup-steps">
          {steps.length ? steps.map((step) => (
            <div className={step.current ? "setup-step current" : step.ok ? "setup-step ok" : "setup-step"} key={step.key}>
              <span>{step.ok ? "✓" : step.current ? "•" : "○"}</span>
              <strong>{step.label}</strong>
              <small>{step.description}</small>
            </div>
          )) : <p className="muted">点击“开始检查”读取部署环境状态。</p>}
        </div>

        <div className="setup-grid">
          <section className="setup-card">
            <div className="setup-card-head">
              <strong>服务环境</strong>
              <span className={setup?.env?.ok ? "status-chip ok" : "status-chip warn"}>{setup?.env?.ok ? "通过" : "待检查"}</span>
            </div>
            <div className="setup-check-list">
              {envChecks.length ? envChecks.map((check) => (
                <details className={`setup-check ${check.ok ? "ok" : "fail"}`} key={check.name}>
                  <summary>
                    <span>{check.ok ? "绿灯" : "红灯"}</span>
                    <strong>{check.name}</strong>
                    <small>{check.user_message}</small>
                  </summary>
                  <p>{check.detail}</p>
                  {check.fix ? <code>{check.fix}</code> : null}
                </details>
              )) : <p className="muted">尚未执行完整环境检查。</p>}
            </div>
          </section>

          <section className="setup-card">
            <div className="setup-card-head">
              <strong>设备准入</strong>
              <select value={selectedDeviceId} onChange={(event) => onSelectDevice(event.target.value)}>
                {(setup?.devices || []).map((device) => (
                  <option key={device.device_id} value={device.device_id}>
                    {device.device_id} · {device.avd_name}
                  </option>
                ))}
              </select>
            </div>
            {selectedDevice ? (
              <div className="setup-device-status">
                <StatusLine ok={selectedEmulatorReady} label="模拟器" text={selectedEmulatorMessage} />
                <StatusLine ok={selectedDevice.emulator?.unlocked} label="解锁" text={selectedDevice.emulator?.unlocked ? "已解锁" : "需要手动解锁"} />
                <StatusLine ok={selectedDevice.google_state?.ok} label="Google" text={selectedDevice.google_state?.user_message || "未检查"} />
                <StatusLine ok={selectedDevice.frida_state?.ok} label="Frida" text={selectedDevice.frida_state?.detail || "未检查"} />
                <StatusLine ok={hasApp} label="应用" text={hasApp ? `${apps.length} 个应用可选` : "请上传 APK 或添加应用"} />
                <StatusLine ok={setup?.validation_passed} label="冒烟" text={setup?.validation_passed ? "已有抓包校验通过" : "需要完成一次抓包校验"} />
              </div>
            ) : (
              <p className="muted">未读取到设备池。</p>
            )}
          </section>
        </div>

        <div className="actions setup-actions">
          <button onClick={onCheck} disabled={loading}>{setup?.checked ? "重新检查" : "开始检查"}</button>
          <button className="secondary" onClick={onStartDevice} disabled={loading}>启动模拟器</button>
          <button className="secondary" onClick={onOpenPreview} disabled={loading || !selectedDevice}>
            查看模拟器
          </button>
          <button className="secondary" onClick={onOpenGoogleLogin} disabled={loading || selectedDevice?.google_state?.ok}>去登录 Google</button>
          <button className="secondary" onClick={onPrepareFrida} disabled={loading || !selectedDevice?.emulator?.adb_online}>启动 Frida</button>
          <label className={loading ? "file-button disabled" : "file-button"}>
            上传生产包 APK
            <input
              type="file"
              accept=".apk,.apks,.zip"
              disabled={loading}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) onInstall("production", file);
                event.target.value = "";
              }}
            />
          </label>
          <label className={loading ? "file-button disabled" : "file-button secondary-upload"}>
            上传测试包 APK
            <input
              type="file"
              accept=".apk,.apks,.zip"
              disabled={loading}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) onInstall("test", file);
                event.target.value = "";
              }}
            />
          </label>
          <button className="secondary" onClick={onValidate} disabled={loading || !selectedApp}>启动抓包测试</button>
          <button onClick={onComplete} disabled={loading || !setup?.ready_to_complete}>完成初始化</button>
        </div>
      </Panel>
    </section>
  );
}

function StatusLine({ ok, label, text }) {
  return (
    <div className={ok ? "setup-status-line ok" : "setup-status-line warn"}>
      <span className={ok ? "state-dot ok" : "state-dot warn"} aria-hidden="true" />
      <strong>{label}</strong>
      <small>{text}</small>
    </div>
  );
}

function DevicePool({ devices, selectedDeviceId, onSelect }) {
  if (!devices.length) {
    return <p className="muted">设备池读取中...</p>;
  }

  return (
    <div className="device-pool" aria-label="设备池">
      {devices.map((device) => {
        const state = deviceState(device);
        return (
          <button
            type="button"
            key={device.device_id}
            className={device.device_id === selectedDeviceId ? "device-card selected" : "device-card"}
            onClick={() => onSelect(device.device_id)}
            title={device.google_state?.user_message || googleStateLabel(device.google_state)}
          >
            <span className={`state-dot ${state.className}`} aria-hidden="true" />
            <strong>{device.device_id}</strong>
            <small>{device.adb_serial}</small>
            <em>{state.label} · {googleStateLabel(device.google_state)}</em>
          </button>
        );
      })}
    </div>
  );
}

function GoogleStatePanel({ state, loading, onOpenLogin }) {
  const stateClass = googleStateClass(state);
  return (
    <section className={`google-state-card ${stateClass}`}>
      <div>
        <span className={`state-dot ${stateClass}`} aria-hidden="true" />
        <strong>{googleStateLabel(state)}</strong>
        <small>{state?.user_message || "启动模拟器后会检查 Google Play 和 Google 账号状态。"}</small>
        {state?.fix ? <small>{state.fix}</small> : null}
      </div>
      <button className="secondary" onClick={onOpenLogin} disabled={loading || state?.ok}>
        去登录 Google
      </button>
    </section>
  );
}

function readinessTitle(state) {
  return {
    ok: "校验通过",
    warn: "等待校验",
    fail: "校验失败",
  }[state] || "未校验";
}

function AppVersionPanel({ app, loading, canCapture, canInstall, installDisabledReason, onSync, onValidate, onInstall }) {
  const [uploadEnvironment, setUploadEnvironment] = useState(app?.environment || "production");

  useEffect(() => {
    if (app) {
      setUploadEnvironment(app.environment || "production");
    }
  }, [app?.id, app?.environment]);

  if (!app) return null;
  const validationStatus = app.last_validation_status || "";
  const validationClass = validationStatus === "passed" ? "ok" : validationStatus === "failed" ? "fail" : "warn";
  const rows = [
    ["包类型", appEnvironmentLabel(app.environment)],
    ["版本", appVersionLabel(app)],
    ["安装时间", app.last_update_time || "-"],
    ["安装来源", app.installer_package || "-"],
    ["签名", app.signature_hint || "-"],
  ];

  return (
    <section className="version-card">
      <div className="version-head">
        <div>
          <span className="panel-eyebrow">Version</span>
          <strong>应用更新与校验</strong>
        </div>
        <span className={`status-chip ${validationClass}`}>{validationLabel(validationStatus)}</span>
      </div>
      <dl className="version-grid">
        {rows.map(([label, value]) => (
          <React.Fragment key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </React.Fragment>
        ))}
      </dl>
      {app.last_validation_message ? <p className="version-message">{app.last_validation_message}</p> : null}
      {installDisabledReason ? <p className="version-message warning">{installDisabledReason}</p> : null}
      <div className="actions version-actions">
        <label className="upload-target">
          上传类型
          <select
            value={uploadEnvironment}
            disabled={loading || !canInstall}
            onChange={(event) => setUploadEnvironment(event.target.value)}
          >
            <option value="production">生产包</option>
            <option value="test">测试包</option>
          </select>
        </label>
        <label className={loading || !canInstall ? "file-button disabled" : "file-button"}>
          上传{appEnvironmentLabel(uploadEnvironment)}更新包
          <input
            type="file"
            accept=".apk,.apks,.zip"
            disabled={loading || !canInstall}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onInstall(uploadEnvironment, file);
              event.target.value = "";
            }}
          />
        </label>
        <button className="secondary" onClick={onSync} disabled={loading || !canCapture}>同步版本</button>
        <button className="secondary" onClick={onValidate} disabled={loading || !canCapture}>重新校验</button>
      </div>
    </section>
  );
}

function ReadinessPanel({ readiness, loading }) {
  const state = readiness?.state || "warn";
  const checks = readiness?.checks || [];
  return (
    <section className={`readiness-card ${state}`}>
      <div className="readiness-head">
        <div>
          <span className={`state-dot ${state}`} aria-hidden="true" />
          <strong>校验状态</strong>
        </div>
        <span>{loading ? "检查中..." : readinessTitle(state)}</span>
      </div>
      {checks.length ? (
        <div className="readiness-grid">
          {checks.map((check) => (
            <details className={`readiness-item ${check.state}`} key={check.name}>
              <summary>
                <span className={`state-dot ${check.state}`} aria-hidden="true" />
                <strong>{check.label}</strong>
                <small>{check.summary}</small>
              </summary>
              {check.detail ? <p>{check.detail}</p> : null}
            </details>
          ))}
        </div>
      ) : (
        <p className="muted">选择应用后会自动检查模拟器、前台 App、Frida、抓包链路和接口捕获状态。</p>
      )}
    </section>
  );
}

function NetworkDiagnostics({ diagnostics, loading, onCheck, onMaintenance, onCapture }) {
  const summary = preflightSummary(diagnostics?.preflight);
  const visiblePorts = (diagnostics?.preflight?.ports || []).filter((item) => !item.ok || item.state !== "free").slice(0, 8);
  return (
    <section className="network-diagnostics">
      <div className="network-diagnostics-head">
        <div>
          <strong>端口 / 网络检查</strong>
          <small>检查服务器端口是否被其他项目占用，并切换模拟器维护网络或抓包网络。</small>
        </div>
        <span className={summary.ok ? "status-chip ok" : "status-chip fail"}>{summary.label}</span>
      </div>
      <div className="network-mode-row">
        <span>当前网络</span>
        <strong>{networkModeLabel(diagnostics?.network)}</strong>
        <small>{diagnostics?.network?.user_message || "点击检查后显示当前模拟器代理状态。"}</small>
      </div>
      {visiblePorts.length ? (
        <div className="port-list">
          {visiblePorts.map((port) => (
            <div className={port.ok ? "port-item ok" : "port-item fail"} key={`${port.port}-${port.label}`}>
              <strong>{port.port}</strong>
              <span>{port.label}</span>
              <em>{port.state}</em>
            </div>
          ))}
        </div>
      ) : null}
      <div className="actions">
        <button className="secondary" onClick={onCheck} disabled={loading}>检查端口/网络</button>
        <button className="secondary" onClick={onMaintenance} disabled={loading}>维护网络</button>
        <button className="secondary" onClick={onCapture} disabled={loading}>抓包网络</button>
      </div>
    </section>
  );
}

function ActionToast({ message, onClose }) {
  useEffect(() => {
    const delay = actionMessageAutoDismissMs(message);
    if (!delay) return undefined;
    const timer = window.setTimeout(onClose, delay);
    return () => window.clearTimeout(timer);
  }, [message.kind, message.title, message.summary, message.detail, onClose]);

  return (
    <aside className={`toast ${message.kind}`} role={message.kind === "error" ? "alert" : "status"}>
      <div className="toast-head">
        <strong>{message.title}</strong>
      </div>
      <p>{message.summary}</p>
      {message.detail ? (
        <details>
          <summary>查看详细诊断</summary>
          <pre>{message.detail}</pre>
        </details>
      ) : null}
    </aside>
  );
}

function Panel({ title, children, className = "", eyebrow, actions = null }) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <div>
          {eyebrow && <span className="panel-eyebrow">{eyebrow}</span>}
          <h2>{title}</h2>
        </div>
        {actions ? <div className="panel-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

function AppGroupList({ groupedApps, selectedAppId, onSelect }) {
  const groups = [
    ["production", "生产包", groupedApps.production],
    ["test", "测试包", groupedApps.test],
  ];

  return (
    <div className="app-groups">
      {groups.map(([key, label, items]) => (
        <details className="app-group" key={key} open={items.some((item) => String(item.id) === String(selectedAppId))}>
          <summary className="app-group-head">
            <span>{label}</span>
            <small>{items.length}</small>
          </summary>
          {items.length ? (
            <div className="app-button-list">
              {items.map((item) => (
                <button
                  type="button"
                  className={String(item.id) === String(selectedAppId) ? "app-list-button selected" : "app-list-button"}
                  key={item.id}
                  onClick={() => onSelect(String(item.id))}
                >
                  <strong>{item.name}</strong>
                  <code>{item.package_name}</code>
                </button>
              ))}
            </div>
          ) : (
            <p className="muted compact-hint">暂无{label}，可通过“添加应用”保存。</p>
          )}
        </details>
      ))}
    </div>
  );
}

function stateText(value) {
  return value ? "是" : "否";
}

function EmulatorView({ emulator }) {
  if (!emulator) return <p className="muted">模拟器状态读取中...</p>;
  const ready = emulator.adb_online && emulator.boot_completed;
  const rows = [
    ["AVD", emulator.avd_name],
    ["ADB Serial", emulator.adb_serial],
    ["进程运行", stateText(emulator.process_running)],
    ["ADB 在线", stateText(emulator.adb_online)],
    ["系统启动完成", stateText(emulator.boot_completed)],
    ["已解锁", stateText(emulator.unlocked)],
    ["当前 AVD", emulator.current_avd || "-"],
  ];
  return (
    <div className={ready ? "emulator-card ready" : "emulator-card"}>
      <div className="emulator-head">
        <strong>保留模拟器</strong>
        <span className={ready ? "badge" : "badge muted-badge"}>{ready ? "可用" : "未就绪"}</span>
      </div>
      <dl className="status compact">
        {rows.map(([label, value]) => (
          <React.Fragment key={label}>
            <dt>{label}</dt>
            <dd>{value || "-"}</dd>
          </React.Fragment>
        ))}
      </dl>
      {emulator.log_file && <small>日志：{emulator.log_file}</small>}
    </div>
  );
}

function StatusView({ status }) {
  if (!status) return <p className="muted">读取中...</p>;
  const rows = [
    ["健康状态", status.health],
    ["模式", status.mode],
    ["包名", status.package],
    ["代理端口", status.proxy],
    ["exporter", status.exporter],
    ["Frida hook", status.frida_hook],
    ["Android proxy", status.android_proxy],
    ["前台窗口", status.foreground],
  ];
  return (
    <dl className="status">
      {rows.map(([label, value]) => (
        <React.Fragment key={label}>
          <dt>{label}</dt>
          <dd>{value || "-"}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

function FlowAnalysis({ flows, filteredFlows, sourceFlowCount, isCleared, filter, onFilterChange, details, curls, expandedFlows, flowTabs, onToggleFlow, onChangeFlowTab, onLoadDetail }) {
  if (flows.length === 0) {
    return (
      <div className="empty-state compact-empty">
        <strong>{isCleared && sourceFlowCount > 0 ? "当前接口列表已清空" : "当前任务还没有 candidates.tsv 业务接口"}</strong>
        <p>{isCleared && sourceFlowCount > 0 ? "抓包仍在运行；继续操作 App 后，新产生的请求会继续实时显示。" : "操作 App 后，业务接口会在这里实时刷新。"}</p>
      </div>
    );
  }
  const methodOptions = methodFilterOptions(flows);

  return (
    <div className="analysis">
      <FlowFilters filter={filter} methodOptions={methodOptions} onChange={onFilterChange} />
      <FlowList
        flows={filteredFlows}
        details={details}
        curls={curls}
        expandedFlows={expandedFlows}
        flowTabs={flowTabs}
        onToggleFlow={onToggleFlow}
        onChangeFlowTab={onChangeFlowTab}
        onLoadDetail={onLoadDetail}
      />
    </div>
  );
}

function FlowFilters({ filter, methodOptions, onChange }) {
  return (
    <div className="flow-filters">
      <div className="flow-method-tabs" aria-label="请求方法统计">
        {methodOptions.map((item) => (
          <button
            type="button"
            key={item.value}
            className={(filter.method || "all") === item.value ? "active" : ""}
            onClick={() => onChange({ ...filter, method: item.value })}
          >
            <span>{item.label}</span>
            <strong>{item.count}</strong>
          </button>
        ))}
      </div>
      <label>
        细分
        <select value={filter.detail || "all"} onChange={(event) => onChange({ ...filter, detail: event.target.value })}>
          {FLOW_DETAIL_FILTERS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
      </label>
      <label>
        Host
        <input value={filter.host} onChange={(event) => onChange({ ...filter, host: event.target.value })} placeholder="按域名过滤" />
      </label>
      <label>
        Path
        <input value={filter.path} onChange={(event) => onChange({ ...filter, path: event.target.value })} placeholder="按路径或 URL 过滤" />
      </label>
    </div>
  );
}

function FlowList({ flows, details, curls, expandedFlows, flowTabs, onToggleFlow, onChangeFlowTab, onLoadDetail }) {
  return (
    <div className="flow-list">
      {flows.map((flow) => (
        <FlowRow
          key={flow.id}
          flow={flow}
          detail={details[flow.id]}
          curl={curls[flow.id]}
          isOpen={Boolean(expandedFlows[flow.id])}
          activeTab={flowTabs[flow.id] || "request"}
          onToggleOpen={onToggleFlow}
          onChangeTab={onChangeFlowTab}
          onLoadDetail={onLoadDetail}
        />
      ))}
      {flows.length === 0 && <p className="muted">当前筛选条件下没有接口记录。</p>}
    </div>
  );
}

function FlowRow({ flow, detail, curl, isOpen, activeTab, onToggleOpen, onChangeTab, onLoadDetail }) {
  const statusClass = String(flow.status) === "200" ? "ok" : String(flow.status) === "NO_RESPONSE" ? "warn" : "neutral";
  const categoryLabel = {
    business: "业务",
    other: "其他",
    asset: "素材",
    noise: "噪声",
  }[flow.category] || "其他";
  const toggleOpen = () => {
    const nextOpen = !isOpen;
    onToggleOpen(flow, nextOpen);
    if (nextOpen) {
      onChangeTab(flow.id, activeTab || "request");
      onLoadDetail(flow);
    }
  };

  return (
    <article className={`flow-card ${flow.category} ${isOpen ? "open" : ""}`}>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={isOpen}
        className="flow-toggle"
        onClick={toggleOpen}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleOpen();
          }
        }}
      >
        <div className="flow-main">
          <span className="flow-time">{compactFlowTime(flow.time)}</span>
          <span className="method">{flow.method || "-"}</span>
          <span className={`status-pill ${statusClass}`}>{flow.status || "-"}</span>
          <span className="timing-pill">{flowTimingSummary(flow)}</span>
          <span className={`category-pill ${flow.category}`}>{categoryLabel}</span>
          <code className="flow-path">{flowPath(flow)}</code>
        </div>
      </div>
      {isOpen && detail ? (
        <FlowDetailPanel
          detail={detail}
          curl={curl || ""}
          activeTab={activeTab || "request"}
          onTabChange={(tab) => onChangeTab(flow.id, tab)}
        />
      ) : isOpen ? (
        <div className="flow-loading">正在加载请求与响应详情...</div>
      ) : null}
    </article>
  );
}

function FlowDetailPanel({ detail, curl, activeTab, onTabChange }) {
  const summary = detail.meta_json?.summary || {};
  const timing = flowTimingInfo(detail);
  const timingRows = flowTimingRows(detail);
  const requestInfo = {
    time: detail.time || "",
    method: detail.method || "",
    url: detail.url || "",
    host: detail.host || summary.host || "",
    path: detail.path || summary.path || "",
    content_type: summary.request_content_type || "",
    request_started_at: detail.request_started_at || "",
    request_finished_at: detail.request_finished_at || "",
    request_duration: timing.request_duration,
    wait_for_response: timing.wait_duration,
    total_duration: timing.total_duration,
  };
  const responseInfo = {
    time: detail.time || "",
    status: detail.status || "",
    url: detail.url || "",
    host: detail.host || summary.host || "",
    path: detail.path || summary.path || "",
    content_type: summary.response_content_type || "",
    no_response: String(detail.status) === "NO_RESPONSE",
    response_started_at: detail.response_started_at || "",
    response_finished_at: detail.response_finished_at || "",
    response_duration: timing.response_duration,
    total_duration: timing.total_duration,
  };
  const requestFiles = {
    meta: detail.files?.meta || "",
    request: detail.files?.request || "",
    request_json: detail.files?.request_json || "",
  };
  const responseFiles = {
    meta: detail.files?.meta || "",
    response: detail.files?.response || "",
    response_json: detail.files?.response_json || "",
  };
  const responseBody =
    String(detail.status) === "NO_RESPONSE" && !detail.response_json && !detail.response_text
      ? "未捕获响应"
      : formatJson(detail.response_json ?? detail.response_text);

  return (
    <div className="detail">
      <section className="flow-timing-panel" aria-label="接口请求响应时间">
        {timingRows.map(([label, value]) => (
          <div key={label} className="flow-timing-item">
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </section>
      <div className="detail-tabs" role="tablist" aria-label="接口详情类型">
        <button className={activeTab === "request" ? "active" : ""} onClick={() => onTabChange("request")} type="button">
          Request
        </button>
        <button className={activeTab === "response" ? "active" : ""} onClick={() => onTabChange("response")} type="button">
          Response
        </button>
      </div>
      {activeTab === "request" ? (
        <div className="detail-stack">
          <section>
            <h3>Request Info</h3>
            <pre>{formatJson(requestInfo)}</pre>
          </section>
          <section>
            <h3>Request Headers</h3>
            <pre>{formatJson(summary.request_headers || [])}</pre>
          </section>
          <section>
            <h3>Request Body</h3>
            <pre>{formatJson(detail.request_json ?? detail.request_text)}</pre>
          </section>
          <section>
            <h3>Request Files</h3>
            <pre>{formatJson(requestFiles)}</pre>
          </section>
          <section>
            <h3>cURL</h3>
            <pre>{curl || "无"}</pre>
          </section>
        </div>
      ) : (
        <div className="detail-stack">
          <section>
            <h3>Response Info</h3>
            <pre>{formatJson(responseInfo)}</pre>
          </section>
          <section>
            <h3>Response Headers</h3>
            <pre>{formatJson(summary.response_headers || [])}</pre>
          </section>
          <section>
            <h3>Response Body</h3>
            <pre>{responseBody}</pre>
          </section>
          <section>
            <h3>Response Files</h3>
            <pre>{formatJson(responseFiles)}</pre>
          </section>
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);

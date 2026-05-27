import { normalizeAppEnvironment } from "./appEnvironment.js";

export function buildUploadInstallPath(environment, filename, deviceId = "") {
  const params = new URLSearchParams({
    environment: normalizeAppEnvironment(environment),
    filename: filename || "upload.apk",
  });
  if (deviceId) {
    params.set("device_id", deviceId);
  }
  return `/api/apps/install?${params.toString()}`;
}

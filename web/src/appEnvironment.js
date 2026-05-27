const ENVIRONMENT_LABELS = {
  production: "生产包",
  test: "测试包",
};

export function normalizeAppEnvironment(value) {
  return value === "test" ? "test" : "production";
}

export function appEnvironmentLabel(value) {
  return ENVIRONMENT_LABELS[normalizeAppEnvironment(value)];
}

export function groupAppsByEnvironment(apps) {
  return apps.reduce(
    (groups, app) => {
      groups[normalizeAppEnvironment(app.environment)].push(app);
      return groups;
    },
    { production: [], test: [] },
  );
}

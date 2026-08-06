use serde::Serialize;
use std::{
    env,
    fs::{self, File},
    net::TcpListener,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};
use tauri::{Manager, RunEvent};

#[derive(Default)]
struct BackendState {
    child: Mutex<Option<Child>>,
    url: Mutex<Option<String>>,
    log_path: Mutex<Option<PathBuf>>,
}

#[derive(Serialize)]
struct DesktopBackendInfo {
    url: Option<String>,
    log_path: Option<String>,
    running: bool,
}

#[tauri::command]
fn desktop_backend_info(state: tauri::State<BackendState>) -> DesktopBackendInfo {
    let running = state
        .child
        .lock()
        .ok()
        .and_then(|guard| guard.as_ref().map(|child| child.id() > 0))
        .unwrap_or(false);
    let url = state.url.lock().ok().and_then(|guard| guard.clone());
    let log_path = state
        .log_path
        .lock()
        .ok()
        .and_then(|guard| guard.as_ref().map(|path| path.display().to_string()));
    DesktopBackendInfo {
        url,
        log_path,
        running,
    }
}

fn main() {
    tauri::Builder::default()
        .manage(BackendState::default())
        .invoke_handler(tauri::generate_handler![desktop_backend_info])
        .setup(|app| {
            let handle = app.handle().clone();
            thread::spawn(move || {
                if let Err(error) = start_backend_and_open_console(handle.clone()) {
                    show_startup_error(&handle, &error);
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build Tauri application")
        .run(|app_handle, event| {
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                stop_backend(app_handle);
            }
        });
}

fn start_backend_and_open_console(app: tauri::AppHandle) -> Result<(), String> {
    let app_data_dir = app
        .path()
        .app_data_dir()
        .map_err(|error| format!("failed to resolve app data directory: {error}"))?;
    let runtime_dir = app_data_dir.join("runtime");
    let config_dir = app_data_dir.join("config");
    let log_dir = runtime_dir.join("logs");
    fs::create_dir_all(&log_dir).map_err(|error| format!("failed to create log directory: {error}"))?;
    fs::create_dir_all(&config_dir)
        .map_err(|error| format!("failed to create config directory: {error}"))?;

    let port = select_console_port()?;
    let url = format!("http://127.0.0.1:{port}/");
    let root_dir = bundled_root_dir(&app)?;
    let launcher = root_dir.join("desktop").join("start-backend.sh");
    if !launcher.exists() {
        return Err(format!("desktop backend launcher is missing: {}", launcher.display()));
    }

    let log_path = log_dir.join("desktop-backend.log");
    let stdout = File::create(&log_path)
        .map_err(|error| format!("failed to create backend log file: {error}"))?;
    let stderr = stdout
        .try_clone()
        .map_err(|error| format!("failed to clone backend log file: {error}"))?;
    let config_path = config_dir.join("local.json");

    let mut command = Command::new("/bin/bash");
    command
        .arg(&launcher)
        .env("TRACEDECK_ROOT", &root_dir)
        .env("CAPTURE_RUNTIME_DIR", &runtime_dir)
        .env("TRACEDECK_CONFIG", &config_path)
        .env("TRACEDECK_DESKTOP", "1")
        .env("CONSOLE_HOST", "127.0.0.1")
        .env("CONSOLE_PORT", port.to_string())
        .env("PATH", desktop_path())
        .stdin(Stdio::null())
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr));

    let child = command
        .spawn()
        .map_err(|error| format!("failed to start backend: {error}"))?;

    {
        let state = app.state::<BackendState>();
        *state
            .child
            .lock()
            .map_err(|_| "backend state lock poisoned".to_string())? = Some(child);
        *state
            .url
            .lock()
            .map_err(|_| "backend state lock poisoned".to_string())? = Some(url.clone());
        *state
            .log_path
            .lock()
            .map_err(|_| "backend state lock poisoned".to_string())? = Some(log_path.clone());
    }

    wait_for_backend(&url, Duration::from_secs(180))
        .map_err(|error| format!("{error}; log={}", log_path.display()))?;
    if let Some(window) = app.get_webview_window("main") {
        let escaped_url = format!("{url:?}");
        window
            .eval(&format!("window.location.replace({escaped_url});"))
            .map_err(|error| format!("failed to navigate desktop window: {error}"))?;
    }
    Ok(())
}

fn bundled_root_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    if let Ok(root) = env::var("TRACEDECK_ROOT") {
        return Ok(PathBuf::from(root));
    }
    if cfg!(debug_assertions) {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        return manifest_dir
            .parent()
            .map(Path::to_path_buf)
            .ok_or_else(|| "failed to resolve development project root".to_string());
    }
    app.path()
        .resource_dir()
        .map_err(|error| format!("failed to resolve bundled resources: {error}"))
}

fn select_console_port() -> Result<u16, String> {
    for port in 7001..=7099 {
        if TcpListener::bind(("127.0.0.1", port)).is_ok() {
            return Ok(port);
        }
    }
    Err("no available local console port in range 7001-7099".to_string())
}

fn wait_for_backend(url: &str, timeout: Duration) -> Result<(), String> {
    let status_url = format!("{url}api/status");
    let started = Instant::now();
    while started.elapsed() < timeout {
        match ureq::get(&status_url).timeout(Duration::from_secs(2)).call() {
            Ok(response) if response.status() < 500 => return Ok(()),
            Ok(_) | Err(_) => thread::sleep(Duration::from_millis(500)),
        }
    }
    Err(format!("timed out waiting for backend: {status_url}"))
}

fn desktop_path() -> String {
    let mut paths = vec![
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    .into_iter()
    .map(String::from)
    .collect::<Vec<_>>();
    if let Ok(existing) = env::var("PATH") {
        paths.push(existing);
    }
    paths.join(":")
}

fn show_startup_error(app: &tauri::AppHandle, message: &str) {
    if let Some(window) = app.get_webview_window("main") {
        let escaped_message = format!("{message:?}");
        let _ = window.eval(&format!(
            "window.__showDesktopError && window.__showDesktopError({escaped_message});"
        ));
    }
}

fn stop_backend(app: &tauri::AppHandle) {
    let child = app
        .state::<BackendState>()
        .child
        .lock()
        .ok()
        .and_then(|mut child_guard| child_guard.take());
    if let Some(mut child) = child {
        let _ = child.kill();
        let _ = child.wait();
    }
}

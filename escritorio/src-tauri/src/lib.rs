//! Seudónimo · ventana de escritorio.
//!
//! Al arrancar elige un puerto libre de 127.0.0.1 y un token aleatorio, y pone en marcha el
//! servicio local (Python, incluido en el paquete) con ambos. La interfaz pide la conexión con
//! el comando `conexion` y habla con el servicio por HTTP local con ese token. Al cerrar la
//! ventana, el servicio se detiene; además, el servicio vigila este proceso y se apaga si
//! desaparece.

use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use serde::Serialize;
use tauri::{Manager, RunEvent};

#[derive(Clone, Serialize)]
struct Conexion {
    puerto: u16,
    token: String,
}

struct Servicio {
    conexion: Conexion,
    hijo: Mutex<Option<Child>>,
    error: Mutex<Option<String>>,
}

#[tauri::command]
fn conexion(estado: tauri::State<Servicio>) -> Result<Conexion, String> {
    if let Some(e) = estado.error.lock().unwrap().clone() {
        return Err(e);
    }
    Ok(estado.conexion.clone())
}

fn token() -> String {
    let mut b = [0u8; 32];
    getrandom::getrandom(&mut b).expect("sin generador aleatorio");
    b.iter().map(|x| format!("{:02x}", x)).collect()
}

fn puerto_libre() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .and_then(|l| l.local_addr())
        .map(|a| a.port())
        .unwrap_or(8780)
}

/// Python y el núcleo: en el paquete, dentro de los recursos; en desarrollo, junto al repositorio.
fn rutas(app: &tauri::App) -> (PathBuf, PathBuf, PathBuf) {
    let recursos = app
        .path()
        .resource_dir()
        .map(|r| r.join("recursos"))
        .unwrap_or_default();
    let python = if cfg!(windows) {
        recursos.join("python").join("python.exe")
    } else {
        recursos.join("python").join("bin").join("python3")
    };
    if python.exists() {
        return (python, recursos.join("nucleo").join("servidor.py"), recursos);
    }
    // desarrollo: el Python del entorno virtual del repositorio (o SEUDONIMO_PYTHON)
    let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..");
    let py = std::env::var("SEUDONIMO_PYTHON").map(PathBuf::from).unwrap_or_else(|_| {
        if cfg!(windows) {
            repo.join(".venv").join("Scripts").join("python.exe")
        } else {
            repo.join(".venv").join("bin").join("python")
        }
    });
    (py, repo.join("nucleo").join("servidor.py"), repo)
}

fn arrancar(app: &tauri::App, c: &Conexion) -> Result<Child, String> {
    let (python, servidor, raiz) = rutas(app);
    let mut cmd = Command::new(&python);
    cmd.arg("-s")
        .arg(&servidor)
        .env("SEUDONIMO_PUERTO", c.puerto.to_string())
        .env("SEUDONIMO_TOKEN", &c.token)
        .env("SEUDONIMO_PADRE", std::process::id().to_string())
        .env("SEUDONIMO_RAIZ", &raiz)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    cmd.spawn()
        .map_err(|e| format!("No se ha podido arrancar el servicio local ({}): {}", python.display(), e))
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let c = Conexion { puerto: puerto_libre(), token: token() };
            let (hijo, error) = match arrancar(app, &c) {
                Ok(h) => (Some(h), None),
                Err(e) => (None, Some(e)),
            };
            app.manage(Servicio { conexion: c, hijo: Mutex::new(hijo), error: Mutex::new(error) });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![conexion])
        .build(tauri::generate_context!())
        .expect("error al construir la aplicación");

    app.run(|app, ev| {
        if let RunEvent::Exit = ev {
            if let Some(s) = app.try_state::<Servicio>() {
                if let Some(mut h) = s.hijo.lock().unwrap().take() {
                    let _ = h.kill();
                    let _ = h.wait();
                }
            }
        }
    });
}

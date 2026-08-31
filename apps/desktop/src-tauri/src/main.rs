#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    if let Some(result) = simplicio_desktop_lib::try_project_discovery_worker()
        .or_else(simplicio_desktop_lib::try_consolidated_token_preflight_worker)
    {
        use std::io::Write;
        let code = match result {
            Ok(report) => {
                let mut output = std::io::stdout().lock();
                if serde_json::to_writer(&mut output, &report).is_ok()
                    && output.write_all(b"\n").is_ok()
                    && output.flush().is_ok()
                {
                    0
                } else {
                    1
                }
            }
            Err(_) => 2,
        };
        std::process::exit(code);
    }
    simplicio_desktop_lib::run();
}

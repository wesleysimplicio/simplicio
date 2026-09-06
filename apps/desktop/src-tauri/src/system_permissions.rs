//! Permission observations belong to the Desktop process, not its Runtime sidecar.
use serde_json::{json, Value};

fn pane(permission: &str) -> Result<&'static str, String> {
    match permission {
        "microphone" => Ok("Privacy_Microphone"),
        "camera" => Ok("Privacy_Camera"),
        "screen" => Ok("Privacy_ScreenCapture"),
        "accessibility" => Ok("Privacy_Accessibility"),
        "files" => Ok("Privacy_AllFiles"),
        "automation" => Ok("Privacy_Automation"),
        "network" => Ok("Privacy_LocalNetwork"),
        "devices" => Ok("Privacy_Bluetooth"),
        _ => Err("permission_invalid".into()),
    }
}

pub fn open_settings(permission: &str) -> Result<(), String> {
    let section = pane(permission)?;
    #[cfg(target_os = "macos")]
    {
        let status = std::process::Command::new("/usr/bin/open")
            .arg(format!("x-apple.systempreferences:com.apple.preference.security?{section}"))
            .status().map_err(|_| "permission_settings_failed")?;
        if status.success() { Ok(()) } else { Err("permission_settings_failed".into()) }
    }
    #[cfg(not(target_os = "macos"))]
    { let _ = section; Err("permission_platform_unsupported".into()) }
}

static MEDIA_REQUEST_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
pub fn request_media(permission: &str) -> Result<Value, String> {
    let _guard = MEDIA_REQUEST_LOCK.try_lock().map_err(|_| "permission_request_pending")?;
    if !matches!(permission, "microphone" | "camera") { return Err("permission_invalid".into()); }
    #[cfg(target_os = "macos")]
    { macos::request(permission)?; Ok(snapshot()) }
    #[cfg(not(target_os = "macos"))]
    { Err("permission_platform_unsupported".into()) }
}

pub fn snapshot() -> Value {
    #[cfg(target_os = "macos")]
    let statuses = macos::read();
    #[cfg(not(target_os = "macos"))]
    let statuses = ["unknown"; 4];
    let ids = ["microphone", "camera", "screen", "accessibility", "files", "automation", "network", "devices"];
    json!({
        "schema": "simplicio.desktop-permissions/v1",
        "source": "operating_system",
        "platform": std::env::consts::OS,
        "rows": ids.iter().enumerate().map(|(i, id)| json!({
            "id": id, "status": statuses.get(i).copied().unwrap_or("unknown"),
            "canOpenSettings": cfg!(target_os = "macos")
        })).collect::<Vec<_>>()
    })
}

#[cfg(target_os = "macos")]
mod macos {
    use objc2::{msg_send, runtime::{AnyClass, AnyObject}};
    #[link(name = "ApplicationServices", kind = "framework")]
    extern "C" { fn AXIsProcessTrusted() -> bool; }
    #[link(name = "CoreGraphics", kind = "framework")]
    extern "C" { fn CGPreflightScreenCaptureAccess() -> bool; }
    #[link(name = "AVFoundation", kind = "framework")]
    extern "C" {
        static AVMediaTypeAudio: *const AnyObject;
        static AVMediaTypeVideo: *const AnyObject;
    }
    fn media_status(media: *const AnyObject) -> &'static str {
        let Some(class) = AnyClass::get(c"AVCaptureDevice") else { return "unknown"; };
        if media.is_null() { return "unknown"; }
        // Read-only public API: it does not request access or start capture.
        let status: isize = unsafe { msg_send![class, authorizationStatusForMediaType: media] };
        match status { 0 => "not_determined", 1 => "restricted", 2 => "denied", 3 => "granted", _ => "unknown" }
    }
    pub fn request(permission: &str) -> Result<(), String> {
        let class = AnyClass::get(c"AVCaptureDevice").ok_or("permission_unavailable")?;
        let media = unsafe { if permission == "microphone" { AVMediaTypeAudio } else { AVMediaTypeVideo } };
        if media_status(media) != "not_determined" { return Ok(()); }
        let (send, receive) = std::sync::mpsc::sync_channel(1);
        let callback = block2::RcBlock::new(move |_granted: objc2::runtime::Bool| { let _ = send.try_send(()); });
        let _: () = unsafe { msg_send![class, requestAccessForMediaType: media, completionHandler: &*callback] };
        receive.recv_timeout(std::time::Duration::from_secs(60)).map_err(|_| "permission_request_pending".to_string())
    }
    pub fn read() -> [&'static str; 4] {
        unsafe {
            [media_status(AVMediaTypeAudio), media_status(AVMediaTypeVideo),
             if CGPreflightScreenCaptureAccess() { "granted" } else { "not_granted" },
             if AXIsProcessTrusted() { "granted" } else { "not_granted" }]
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn settings_target_is_allowlisted() {
        assert_eq!(pane("microphone").unwrap(), "Privacy_Microphone");
        for id in ["https://example.test", "../camera", "camera?inject", ""] {
            assert!(pane(id).is_err());
        }
    }
    #[test]
    fn settings_does_not_accept_a_url_or_shell_command() {
        assert!(open_settings("camera; touch /tmp/no").is_err());
    }
}

use tauri::menu::{Menu, MenuItem, MenuItemKind, Submenu};
use tauri::{Emitter, Manager, Runtime};

const CHECK_UPDATES_MENU_ID: &str = "simplicio.check-for-updates";
const CHECK_UPDATES_LABEL: &str = "Check for Updates...";
const CHECK_UPDATES_EVENT: &str = "simplicio://check-for-updates";
const MAIN_WINDOW_LABEL: &str = "main";

/// Installs the desktop menu without replacing the platform's standard actions.
/// The update item requests the frontend dialog; it never installs an update.
pub fn install<R: Runtime>(app: &tauri::App<R>) -> tauri::Result<()> {
    let menu = Menu::default(app.handle())?;
    let updates = MenuItem::with_id(
        app,
        CHECK_UPDATES_MENU_ID,
        CHECK_UPDATES_LABEL,
        true,
        None::<&str>,
    )?;

    let submenu = update_submenu(&menu)?;
    #[cfg(target_os = "macos")]
    submenu.set_text("Simplicio")?;

    // Tauri's default app menu (macOS) and Help menu (Windows/Linux) put About
    // first. Keep About, Services, Edit shortcuts, Window and Quit intact.
    submenu.insert(&updates, 1)?;
    app.set_menu(menu)?;

    app.on_menu_event(|app, event| {
        let Some((window_label, event_name)) = update_request(event.id().as_ref()) else {
            return;
        };
        let Some(window) = app.get_webview_window(window_label) else {
            eprintln!("Simplicio: update dialog unavailable because the main window is closed");
            return;
        };

        // A window manager may refuse a focus request. Still deliver the event
        // so the dialog is ready when the user brings Simplicio to the front.
        let shown = window.show();
        let restored = window.unminimize();
        let focused = window.set_focus();
        if shown.is_err() || restored.is_err() || focused.is_err() {
            eprintln!("Simplicio: could not bring the update dialog window to the front");
        }
        if app.emit_to(window_label, event_name, ()).is_err() {
            eprintln!("Simplicio: could not deliver the check-for-updates request");
        }
    });

    Ok(())
}

fn update_submenu<R: Runtime>(menu: &Menu<R>) -> tauri::Result<Submenu<R>> {
    let items = menu.items()?;
    #[cfg(target_os = "macos")]
    let item = items.into_iter().next();
    #[cfg(not(target_os = "macos"))]
    let item = items
        .into_iter()
        .find(|item| item.id().as_ref() == tauri::menu::HELP_SUBMENU_ID);

    match item {
        Some(MenuItemKind::Submenu(submenu)) => Ok(submenu),
        _ => Err(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "Simplicio: the standard application or Help menu is unavailable",
        )
        .into()),
    }
}

fn update_request(menu_id: &str) -> Option<(&'static str, &'static str)> {
    (menu_id == CHECK_UPDATES_MENU_ID).then_some((MAIN_WINDOW_LABEL, CHECK_UPDATES_EVENT))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn routes_the_update_item_only_to_the_main_window_event() {
        assert_eq!(
            update_request("simplicio.check-for-updates"),
            Some(("main", "simplicio://check-for-updates"))
        );
    }

    #[test]
    fn leaves_default_actions_and_unrecognized_ids_alone() {
        for id in [
            "",
            "about",
            "copy",
            "paste",
            "quit",
            "Check for Updates...",
            "simplicio.check-for-updates ",
            "Simplicio.check-for-updates",
            "simplicio.install-update",
        ] {
            assert_eq!(update_request(id), None, "unexpected update request: {id}");
        }
    }
}

//! System tray menu handling.

use tauri::{
    image::Image,
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, Runtime,
};

/// Menu item IDs
pub const MENU_STATUS: &str = "status";
pub const MENU_SETTINGS: &str = "settings";
pub const MENU_QUIT: &str = "quit";

// Embed icon as raw PNG bytes
const ICON_PNG: &[u8] = include_bytes!("../assets/icon-32.png");

/// Decode PNG bytes to RGBA
fn decode_png_to_rgba(png_data: &[u8]) -> (Vec<u8>, u32, u32) {
    let decoder = png::Decoder::new(png_data);
    let mut reader = decoder.read_info().expect("invalid PNG");
    let mut buf = vec![0; reader.output_buffer_size()];
    let info = reader
        .next_frame(&mut buf)
        .expect("failed to decode PNG frame");
    let raw = &buf[..info.buffer_size()];

    let rgba = match info.color_type {
        png::ColorType::Rgba => raw.to_vec(),
        png::ColorType::Rgb => {
            let mut out = Vec::with_capacity(raw.len() / 3 * 4);
            for chunk in raw.chunks(3) {
                out.extend_from_slice(chunk);
                out.push(255);
            }
            out
        }
        _ => panic!("unsupported PNG color type for tray icon"),
    };

    (rgba, info.width, info.height)
}

/// Create the system tray menu
pub fn create_tray_menu<R: Runtime>(app: &AppHandle<R>) -> Result<Menu<R>, tauri::Error> {
    let status = MenuItem::with_id(app, MENU_STATUS, "Status: Running", false, None::<&str>)?;
    let settings = MenuItem::with_id(app, MENU_SETTINGS, "Settings...", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, MENU_QUIT, "Quit", true, None::<&str>)?;

    Menu::with_items(app, &[&status, &settings, &quit])
}

/// Set up the system tray
pub fn setup_tray<R: Runtime>(app: &AppHandle<R>) -> Result<(), tauri::Error> {
    let menu = create_tray_menu(app)?;

    let (rgba, width, height) = decode_png_to_rgba(ICON_PNG);
    let icon = Image::new_owned(rgba, width, height);

    let _tray = TrayIconBuilder::new()
        .icon(icon)
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(move |app, event| {
            handle_menu_event(app, event.id.as_ref());
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                if let Some(window) = tray.app_handle().get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        })
        .build(app)?;

    Ok(())
}

/// Handle menu item clicks
fn handle_menu_event<R: Runtime>(app: &AppHandle<R>, menu_id: &str) {
    match menu_id {
        MENU_SETTINGS => {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
        MENU_QUIT => {
            app.exit(0);
        }
        _ => {}
    }
}

use clap::Parser;
use gtk::prelude::*;
use gtk4 as gtk;
use libadwaita as adw;
use log::{error, info};
use std::process::ExitCode;

mod core;
mod gui;

use crate::core::{LEDController, ProfileManager, RGBColor, Zone};

#[derive(Parser, Debug)]
#[command(name = "casper-keyboard-rgb")]
#[command(version = "1.0.1")]
#[command(about = "Casper Excalibur klavye RGB LED kontrol aracı")]
struct Cli {
    /// Son kullanılan profili geri yükle (systemd servisi için)
    #[arg(long)]
    restore: bool,

    /// Ayrıntılı log çıktısı
    #[arg(short, long)]
    verbose: bool,
}

fn restore() -> ExitCode {
    let pm = ProfileManager::new();
    let profile = pm.get_last_used();

    if profile.is_none() {
        info!("Geri yüklenecek profil yok – çıkılıyor.");
        return ExitCode::SUCCESS;
    }

    let p = profile.unwrap();
    let controller = LEDController::new();

    let zone = match p.zone.as_str() {
        "left" => Zone::Left,
        "center" => Zone::Center,
        "right" => Zone::Right,
        _ => Zone::All,
    };

    let color = RGBColor {
        r: p.r,
        g: p.g,
        b: p.b,
    };

    match controller.set_color(zone, p.brightness, color) {
        Ok(_) => {
            if let Some(name) = pm.get_last_used_name() {
                info!("Profil geri yüklendi: {}", name);
            }
            ExitCode::SUCCESS
        }
        Err(e) => {
            error!("Profil geri yüklenemedi: {}", e);
            ExitCode::FAILURE
        }
    }
}

fn start_gui() -> ExitCode {
    let app = adw::Application::builder()
        .application_id("org.casper.keyboard.rgb")
        .build();

    app.connect_activate(gui::build_ui);

    // Filter out CLI args from GTK since we use Clap to parse them
    let empty_args: [&str; 0] = [];
    let exit_status = app.run_with_args(&empty_args);

    if exit_status == gtk::glib::ExitCode::SUCCESS {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

fn main() -> ExitCode {
    let cli = Cli::parse();

    let log_level = if cli.verbose {
        log::LevelFilter::Debug
    } else {
        log::LevelFilter::Info
    };

    env_logger::Builder::new()
        .filter_level(log_level)
        .format_timestamp_millis()
        .init();

    if cli.restore {
        restore()
    } else {
        start_gui()
    }
}

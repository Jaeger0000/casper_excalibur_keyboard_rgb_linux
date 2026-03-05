use adw::prelude::*;
use gtk::prelude::*;
use gtk4 as gtk;
use libadwaita as adw;
use log::{error, info};
use std::cell::RefCell;
use std::rc::Rc;

use crate::core::{LEDController, ProfileManager, RGBColor, Zone};

pub fn build_ui(app: &adw::Application) {
    let controller = Rc::new(LEDController::new());
    let profile_mgr = Rc::new(RefCell::new(ProfileManager::new()));

    let window = adw::ApplicationWindow::builder()
        .application(app)
        .title("Casper Excalibur Klavye RGB")
        .default_width(480)
        .default_height(540)
        .build();

    let content_box = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .build();

    let header_bar = adw::HeaderBar::new();
    content_box.append(&header_bar);

    let main_box = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .spacing(12)
        .margin_top(16)
        .margin_bottom(16)
        .margin_start(16)
        .margin_end(16)
        .build();
    content_box.append(&main_box);

    // ── Preferences Group (for styling) ──
    let pref_group = adw::PreferencesGroup::new();
    main_box.append(&pref_group);

    // ── Color ──
    let color_row = adw::ActionRow::builder()
        .title("Renk")
        .subtitle("LED rengini seçin")
        .build();
    let color_button = gtk::ColorButton::builder()
        .rgba(&gtk::gdk::RGBA::new(1.0, 0.0, 0.0, 1.0))
        .valign(gtk::Align::Center)
        .build();
    color_row.add_suffix(&color_button);
    pref_group.add(&color_row);

    // ── Zone ──
    let zone_row = adw::ActionRow::builder()
        .title("Klavye Bölgesi")
        .subtitle("Hangi bölgenin değişeceğini seçin")
        .build();
    let zone_combo = gtk::DropDown::from_strings(&["Tümü", "Sol", "Orta", "Sağ"]);
    zone_combo.set_valign(gtk::Align::Center);
    zone_row.add_suffix(&zone_combo);
    pref_group.add(&zone_row);

    // ── Brightness ──
    let bright_row = adw::ActionRow::builder()
        .title("Parlaklık")
        .subtitle("LED parlaklık seviyesi")
        .build();
    let bright_scale = gtk::Scale::with_range(gtk::Orientation::Horizontal, 0.0, 2.0, 1.0);
    bright_scale.set_digits(0);
    bright_scale.set_value(2.0);
    bright_scale.set_hexpand(true);
    bright_scale.set_valign(gtk::Align::Center);
    bright_row.add_suffix(&bright_scale);
    pref_group.add(&bright_row);

    // ── Profiles ──
    let profile_group = adw::PreferencesGroup::builder().title("Profiller").build();
    main_box.append(&profile_group);

    let profile_row = adw::ActionRow::builder().build();
    let profile_box = gtk::Box::builder()
        .orientation(gtk::Orientation::Horizontal)
        .spacing(8)
        .build();

    let profile_combo_list = gtk::StringList::new(&[]);
    let profile_dropdown =
        gtk::DropDown::new(Some(profile_combo_list.clone()), gtk::Expression::NONE);
    profile_dropdown.set_valign(gtk::Align::Center);
    profile_box.append(&profile_dropdown);

    let load_btn = gtk::Button::with_label("Yükle");
    load_btn.set_valign(gtk::Align::Center);
    profile_box.append(&load_btn);

    let save_btn = gtk::Button::with_label("Kaydet");
    save_btn.set_valign(gtk::Align::Center);
    profile_box.append(&save_btn);

    let del_btn = gtk::Button::with_label("Sil");
    del_btn.set_valign(gtk::Align::Center);
    profile_box.append(&del_btn);

    profile_row.set_child(Some(&profile_box));
    profile_group.add(&profile_row);

    // ── Action Buttons ──
    let btn_box = gtk::Box::builder()
        .orientation(gtk::Orientation::Horizontal)
        .spacing(12)
        .halign(gtk::Align::Center)
        .margin_top(16)
        .build();

    let apply_btn = gtk::Button::builder()
        .label("Uygula")
        .css_classes(["suggested-action"])
        .build();
    btn_box.append(&apply_btn);

    let off_btn = gtk::Button::builder()
        .label("LED Kapat")
        .css_classes(["destructive-action"])
        .build();
    btn_box.append(&off_btn);

    main_box.append(&btn_box);

    // Status bar (using a label)
    let status_label = gtk::Label::builder()
        .label("Hazır")
        .halign(gtk::Align::Center)
        .margin_top(8)
        .build();
    main_box.append(&status_label);

    window.set_content(Some(&content_box));

    // ── Logic and Callbacks ──

    let get_selected_zone = {
        let zone_combo = zone_combo.clone();
        move || match zone_combo.selected() {
            0 => Zone::All,
            1 => Zone::Left,
            2 => Zone::Center,
            3 => Zone::Right,
            _ => Zone::All,
        }
    };

    let populate_profiles = {
        let profile_mgr = profile_mgr.clone();
        let profile_combo_list = profile_combo_list.clone();
        move || {
            profile_combo_list.splice(0, profile_combo_list.n_items(), &[]);
            let pm = profile_mgr.borrow();
            let mut names: Vec<String> = pm.get_profiles().keys().cloned().collect();
            names.sort();
            for name in names {
                profile_combo_list.append(&name);
            }
        }
    };
    populate_profiles();

    // Load Button
    load_btn.connect_clicked({
        let profile_mgr = profile_mgr.clone();
        let profile_dropdown = profile_dropdown.clone();
        let profile_combo_list = profile_combo_list.clone();
        let color_button = color_button.clone();
        let bright_scale = bright_scale.clone();
        let zone_combo = zone_combo.clone();
        let status_label = status_label.clone();
        move |_| {
            let selected = profile_dropdown.selected();
            if selected == gtk::INVALID_LIST_POSITION {
                return;
            }
            if let Some(obj) = profile_combo_list.item(selected) {
                if let Some(string_obj) = obj.downcast_ref::<gtk::StringObject>() {
                    let name = string_obj.string();
                    let pm = profile_mgr.borrow();
                    if let Some(p) = pm.get_profiles().get(&name.to_string()) {
                        color_button.set_rgba(&gtk::gdk::RGBA::new(
                            p.r as f32 / 255.0,
                            p.g as f32 / 255.0,
                            p.b as f32 / 255.0,
                            1.0,
                        ));
                        bright_scale.set_value(p.brightness as f64);

                        let zone_idx = match p.zone.as_str() {
                            "all" => 0,
                            "left" => 1,
                            "center" => 2,
                            "right" => 3,
                            _ => 0,
                        };
                        zone_combo.set_selected(zone_idx);
                        status_label.set_label(&format!("Profil yüklendi: {}", name));
                    }
                }
            }
        }
    });

    // Save Button
    save_btn.connect_clicked({
        let profile_mgr = profile_mgr.clone();
        let window = window.clone();
        let get_selected_zone = get_selected_zone.clone();
        let bright_scale = bright_scale.clone();
        let color_button = color_button.clone();
        let status_label = status_label.clone();
        let populate_profiles = populate_profiles.clone();
        move |_| {
            let rgba = color_button.rgba();
            let color = RGBColor {
                r: (rgba.red() * 255.0) as i32,
                g: (rgba.green() * 255.0) as i32,
                b: (rgba.blue() * 255.0) as i32,
            };
            let brightness = bright_scale.value() as i32;
            let zone = get_selected_zone();

            let dialog = gtk::MessageDialog::builder()
                .transient_for(&window)
                .modal(true)
                .text("Profil Kaydet")
                .secondary_text("Lütfen profilin adını girin:")
                .buttons(gtk::ButtonsType::OkCancel)
                .build();

            let entry = gtk::Entry::builder()
                .placeholder_text("Profil Adı")
                .margin_top(8)
                .margin_bottom(8)
                .margin_start(8)
                .margin_end(8)
                .build();

            let content_area = dialog.content_area();
            content_area.append(&entry);

            let pm = profile_mgr.clone();
            let status = status_label.clone();
            let pop = populate_profiles.clone();

            dialog.connect_response(move |d, response| {
                if response == gtk::ResponseType::Ok {
                    let name = entry.text();
                    if name.is_empty() {
                        d.destroy();
                        return;
                    }
                    let mgr = pm.borrow();
                    match mgr.save_profile(name.as_str(), zone.as_str(), brightness, color.clone())
                    {
                        Ok(_) => {
                            status.set_label(&format!("Profil kaydedildi: {}", name));
                            drop(mgr);
                            pop();
                        }
                        Err(e) => {
                            status.set_label(&format!("Hata: {}", e));
                        }
                    }
                }
                d.destroy();
            });
            dialog.present();
        }
    });

    // Delete Button
    del_btn.connect_clicked({
        let profile_mgr = profile_mgr.clone();
        let profile_dropdown = profile_dropdown.clone();
        let profile_combo_list = profile_combo_list.clone();
        let status_label = status_label.clone();
        let populate_profiles = populate_profiles.clone();
        move |_| {
            let selected = profile_dropdown.selected();
            if selected == gtk::INVALID_LIST_POSITION {
                return;
            }
            if let Some(obj) = profile_combo_list.item(selected) {
                if let Some(string_obj) = obj.downcast_ref::<gtk::StringObject>() {
                    let name = string_obj.string();
                    let pm = profile_mgr.borrow();
                    if let Ok(true) = pm.delete_profile(name.as_ref()) {
                        status_label.set_label(&format!("Profil silindi: {}", name));
                        drop(pm);
                        populate_profiles();
                    }
                }
            }
        }
    });

    // Apply Button
    apply_btn.connect_clicked({
        let controller = controller.clone();
        let profile_mgr = profile_mgr.clone();
        let color_button = color_button.clone();
        let bright_scale = bright_scale.clone();
        let status_label = status_label.clone();
        let get_selected_zone = get_selected_zone.clone();
        move |_| {
            let rgba = color_button.rgba();
            let color = RGBColor {
                r: (rgba.red() * 255.0) as i32,
                g: (rgba.green() * 255.0) as i32,
                b: (rgba.blue() * 255.0) as i32,
            };
            let brightness = bright_scale.value() as i32;
            let zone = get_selected_zone();

            match controller.set_color(zone.clone(), brightness, color.clone()) {
                Ok(_) => {
                    let msg = format!(
                        "Uygulandı: {:?} | #{} | Parlaklık {}",
                        zone,
                        color.to_hex(),
                        brightness
                    );
                    status_label.set_label(&msg);
                    info!("{}", msg);

                    let pm = profile_mgr.borrow_mut();
                    let _ = pm.save_profile("Son Kullanılan", zone.as_str(), brightness, color);
                    let _ = pm.set_last_used("Son Kullanılan");
                }
                Err(e) => {
                    let msg = format!("Hata: {}", e);
                    status_label.set_label(&msg);
                    error!("{}", msg);
                }
            }
        }
    });

    // Off Button
    off_btn.connect_clicked({
        let controller = controller.clone();
        let status_label = status_label.clone();
        move |_| match controller.turn_off() {
            Ok(_) => {
                status_label.set_label("LED'ler kapatıldı");
                info!("LED'ler kapatıldı");
            }
            Err(e) => {
                let msg = format!("Hata: {}", e);
                status_label.set_label(&msg);
                error!("{}", msg);
            }
        }
    });

    window.present();
}

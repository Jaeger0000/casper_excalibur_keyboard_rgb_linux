use log::{debug, info, warn};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::Command;

// ──────────────────────────────────────────────
// Config Constants
// ──────────────────────────────────────────────
pub const APP_NAME: &str = "casper-keyboard-rgb";
pub const LED_CONTROL_PATH: &str = "/sys/class/leds/casper::kbd_backlight/led_control";
pub const HELPER_SCRIPT_PATH: &str = "/usr/lib/casper-keyboard-rgb/led-write-helper";
pub const MAX_BRIGHTNESS: i32 = 2;
pub const MIN_BRIGHTNESS: i32 = 0;

// ──────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub enum Zone {
    Left,
    Center,
    Right,
    All,
}

impl Zone {
    pub fn value(&self) -> i32 {
        match self {
            Zone::Left => 0x03,
            Zone::Center => 0x04,
            Zone::Right => 0x05,
            Zone::All => 0x06,
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "left" => Some(Zone::Left),
            "center" => Some(Zone::Center),
            "right" => Some(Zone::Right),
            "all" => Some(Zone::All),
            _ => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Zone::Left => "left",
            Zone::Center => "center",
            Zone::Right => "right",
            Zone::All => "all",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RGBColor {
    pub r: i32,
    pub g: i32,
    pub b: i32,
}

impl RGBColor {
    pub fn to_hex(&self) -> String {
        format!("{:02X}{:02X}{:02X}", self.r, self.g, self.b)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Profile {
    pub zone: String,
    pub brightness: i32,
    pub r: i32,
    pub g: i32,
    pub b: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProfilesData {
    #[serde(default)]
    pub profiles: HashMap<String, Profile>,
    #[serde(default)]
    pub last_used: Option<String>,
}

// ──────────────────────────────────────────────
// LED Controller
// ──────────────────────────────────────────────
pub struct LEDController {
    led_path: String,
}

impl Default for LEDController {
    fn default() -> Self {
        Self::new()
    }
}

impl LEDController {
    pub fn new() -> Self {
        Self {
            led_path: LED_CONTROL_PATH.to_string(),
        }
    }

    pub fn set_color(&self, zone: Zone, brightness: i32, color: RGBColor) -> Result<(), String> {
        if !(MIN_BRIGHTNESS..=MAX_BRIGHTNESS).contains(&brightness) {
            return Err(format!(
                "Parlaklık {} ile {} arasında olmalıdır.",
                MIN_BRIGHTNESS, MAX_BRIGHTNESS
            ));
        }

        let command = format!(
            "{}{:02}{:02X}{:02X}{:02X}",
            zone.value(),
            brightness,
            color.r,
            color.g,
            color.b
        );

        let re = Regex::new(r"^[3-6](0[0-2])[0-9A-Fa-f]{6}$").unwrap();
        if !re.is_match(&command) {
            return Err(format!("Oluşturulan komut doğrulanamadı: {}", command));
        }

        self.write_command(&command)
    }

    pub fn turn_off(&self) -> Result<(), String> {
        self.set_color(Zone::All, 0, RGBColor { r: 0, g: 0, b: 0 })
    }

    fn write_command(&self, command: &str) -> Result<(), String> {
        match self.write_direct(command) {
            Ok(_) => {
                info!("Doğrudan yazma başarılı: {}", command);
                Ok(())
            }
            Err(err) => {
                debug!("Doğrudan yazma başarısız, helper deneniyor: {}", err);
                self.write_via_helper(command)
            }
        }
    }

    fn write_direct(&self, command: &str) -> Result<(), String> {
        let path = Path::new(&self.led_path);
        let resolved = fs::canonicalize(path).map_err(|e| e.to_string())?;

        if !resolved.to_string_lossy().starts_with("/sys/") {
            return Err(format!(
                "LED kontrol dosyası /sys/ dışına işaret ediyor: {:?}",
                resolved
            ));
        }

        let mut file = OpenOptions::new()
            .write(true)
            .open(resolved)
            .map_err(|e| format!("Dosya açılamadı (Yetki yok olabilir): {}", e))?;
        file.write_all(command.as_bytes())
            .map_err(|e| format!("LED dosyasına yazılamadı: {}", e))?;

        Ok(())
    }

    fn write_via_helper(&self, command: &str) -> Result<(), String> {
        if !Path::new(HELPER_SCRIPT_PATH).exists() {
            return Err(format!("Yardımcı betik bulunamadı: {}", HELPER_SCRIPT_PATH));
        }

        let output = Command::new("pkexec")
            .arg(HELPER_SCRIPT_PATH)
            .arg(command)
            .output()
            .map_err(|e| format!("pkexec çalıştırılamadı: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!(
                "LED yazma başarısız (exit {}): {}",
                output.status,
                stderr.trim()
            ));
        }

        Ok(())
    }
}

// ──────────────────────────────────────────────
// Profile Manager
// ──────────────────────────────────────────────
pub struct ProfileManager {
    config_dir: PathBuf,
    profiles_file: PathBuf,
}

impl Default for ProfileManager {
    fn default() -> Self {
        Self::new()
    }
}

impl ProfileManager {
    pub fn new() -> Self {
        let home_dir = dirs::home_dir().expect("Home dizini bulunamadı");
        let config_dir = home_dir.join(".config").join(APP_NAME);
        let profiles_file = config_dir.join("profiles.json");

        let pm = Self {
            config_dir,
            profiles_file,
        };
        pm.ensure_storage();
        pm
    }

    fn ensure_storage(&self) {
        if !self.config_dir.exists() {
            if let Err(e) = fs::create_dir_all(&self.config_dir) {
                warn!("Yapılandırma dizini oluşturulamadı: {}", e);
                return;
            }
        }

        if !self.profiles_file.exists() {
            let mut default_profiles = HashMap::new();
            default_profiles.insert(
                "Kırmızı".to_string(),
                Profile {
                    zone: "all".to_string(),
                    brightness: 2,
                    r: 255,
                    g: 0,
                    b: 0,
                },
            );
            default_profiles.insert(
                "Yeşil".to_string(),
                Profile {
                    zone: "all".to_string(),
                    brightness: 2,
                    r: 0,
                    g: 255,
                    b: 0,
                },
            );
            default_profiles.insert(
                "Mavi".to_string(),
                Profile {
                    zone: "all".to_string(),
                    brightness: 2,
                    r: 0,
                    g: 0,
                    b: 255,
                },
            );
            default_profiles.insert(
                "Beyaz".to_string(),
                Profile {
                    zone: "all".to_string(),
                    brightness: 2,
                    r: 255,
                    g: 255,
                    b: 255,
                },
            );
            default_profiles.insert(
                "Mor".to_string(),
                Profile {
                    zone: "all".to_string(),
                    brightness: 2,
                    r: 128,
                    g: 0,
                    b: 255,
                },
            );
            default_profiles.insert(
                "Turuncu".to_string(),
                Profile {
                    zone: "all".to_string(),
                    brightness: 2,
                    r: 255,
                    g: 165,
                    b: 0,
                },
            );
            default_profiles.insert(
                "Kapalı".to_string(),
                Profile {
                    zone: "all".to_string(),
                    brightness: 0,
                    r: 0,
                    g: 0,
                    b: 0,
                },
            );

            let initial_data = ProfilesData {
                profiles: default_profiles,
                last_used: None,
            };

            if let Err(e) = self.write_atomic(&initial_data) {
                warn!("Varsayılan profiller yazılamadı: {}", e);
            } else {
                info!("Varsayılan profiller oluşturuldu: {:?}", self.profiles_file);
            }
        }
    }

    fn read_data(&self) -> ProfilesData {
        if let Ok(mut file) = File::open(&self.profiles_file) {
            let mut contents = String::new();
            if file.read_to_string(&mut contents).is_ok() {
                if let Ok(data) = serde_json::from_str(&contents) {
                    return data;
                }
            }
        }
        ProfilesData {
            profiles: HashMap::new(),
            last_used: None,
        }
    }

    fn write_atomic(&self, data: &ProfilesData) -> Result<(), std::io::Error> {
        let tmp_path = self.profiles_file.with_extension("tmp");
        let content = serde_json::to_string_pretty(data)?;

        let mut file = File::create(&tmp_path)?;
        file.write_all(content.as_bytes())?;

        let mut perms = file.metadata()?.permissions();
        perms.set_mode(0o600);
        file.set_permissions(perms)?;

        fs::rename(&tmp_path, &self.profiles_file)?;
        Ok(())
    }

    pub fn get_profiles(&self) -> HashMap<String, Profile> {
        self.read_data().profiles
    }

    pub fn save_profile(
        &self,
        name: &str,
        zone: &str,
        brightness: i32,
        color: RGBColor,
    ) -> Result<(), String> {
        let mut data = self.read_data();
        data.profiles.insert(
            name.to_string(),
            Profile {
                zone: zone.to_string(),
                brightness,
                r: color.r,
                g: color.g,
                b: color.b,
            },
        );
        self.write_atomic(&data).map_err(|e| e.to_string())
    }

    pub fn delete_profile(&self, name: &str) -> Result<bool, String> {
        let mut data = self.read_data();
        let existed = data.profiles.remove(name).is_some();
        if existed {
            self.write_atomic(&data).map_err(|e| e.to_string())?;
        }
        Ok(existed)
    }

    pub fn set_last_used(&self, name: &str) -> Result<(), String> {
        let mut data = self.read_data();
        data.last_used = Some(name.to_string());
        self.write_atomic(&data).map_err(|e| e.to_string())
    }

    pub fn get_last_used(&self) -> Option<Profile> {
        let data = self.read_data();
        if let Some(name) = &data.last_used {
            if let Some(profile) = data.profiles.get(name) {
                return Some(profile.clone());
            }
        }
        None
    }

    pub fn get_last_used_name(&self) -> Option<String> {
        let data = self.read_data();
        data.last_used
    }
}

pub fn validate_profile_name(name: &str) -> Result<String, String> {
    let name = name.trim().to_string();
    if name.is_empty() {
        return Err("Profil adı boş olamaz.".to_string());
    }
    if name.len() > 30 {
        return Err("Profil adı en fazla 30 karakter olabilir.".to_string());
    }
    Ok(name)
}

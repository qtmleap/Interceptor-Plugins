// Builds the pinned QuickJS bridge into a static library using only std::process::Command.
// The syntax-only entry point (csrc/check.c) includes the unmodified pinned bridge.c, so bridge.c
// is not compiled separately.

use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

const VENDOR: [&str; 5] = [
    "quickjs.c",
    "dtoa.c",
    "libregexp.c",
    "libunicode.c",
    "cutils.c",
];

fn tool_output(program: &str, args: &[&str]) -> String {
    Command::new(program)
        .args(args)
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| {
            String::from_utf8_lossy(&o.stdout)
                .lines()
                .next()
                .unwrap_or("")
                .trim()
                .to_string()
        })
        .unwrap_or_default()
}

fn run(mut command: Command) {
    let status = command
        .status()
        .unwrap_or_else(|e| panic!("failed to run {:?}: {}", command, e));
    if !status.success() {
        panic!("command failed ({}): {:?}", status, command);
    }
}

fn track(path: &Path) {
    println!("cargo:rerun-if-changed={}", path.display());
}

fn main() {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let out = PathBuf::from(env::var("OUT_DIR").unwrap());
    println!("cargo:rerun-if-env-changed=CC");
    println!("cargo:rerun-if-env-changed=AR");
    track(&manifest.join("build.rs"));
    track(&manifest.join("Cargo.toml"));
    track(&manifest.join("Cargo.lock"));
    track(&manifest.join("../../repository-config.json"));
    track(&manifest.join("csrc/check.c"));
    let source =
        manifest.join("../../.tools/interceptor/Packages/InterceptorAutomation/Sources/CQuickJS");
    let source = fs::canonicalize(&source).unwrap_or_else(|e| {
        panic!(
            "pinned CQuickJS source not found at {}: {}",
            source.display(),
            e
        )
    });
    let vendor = source.join("Vendor");
    let include = source.join("include");

    // Track every pinned C source and header.
    for dir in [&source, &vendor, &include] {
        for entry in fs::read_dir(dir).unwrap().flatten() {
            let path = entry.path();
            if path.is_file() {
                track(&path);
            }
        }
    }
    track(&source);
    track(&vendor);

    assert_eq!(
        fs::read_to_string(vendor.join("VERSION")).unwrap().trim(),
        "2026-06-04",
        "review CONFIG_VERSION after repinning"
    );
    let cc = env::var("CC").unwrap_or_else(|_| "cc".into());
    let ar = env::var("AR").unwrap_or_else(|_| "ar".into());

    let mut sources: Vec<(PathBuf, PathBuf)> =
        vec![(manifest.join("csrc/check.c"), out.join("check.o"))];
    for name in VENDOR {
        sources.push((vendor.join(name), out.join(name.replace(".c", ".o"))));
    }
    let mut objects = Vec::new();
    for (src, obj) in &sources {
        let mut c = Command::new(&cc);
        c.args([
            "-c",
            "-O2",
            "-std=gnu11",
            "-fwrapv",
            "-funsigned-char",
            "-fPIC",
            "-D_GNU_SOURCE",
        ])
        .arg("-DCONFIG_VERSION=\"2026-06-04\"")
        .arg("-I")
        .arg(&include)
        .arg("-I")
        .arg(&vendor)
        .arg("-I")
        .arg(&source)
        .arg("-o")
        .arg(obj)
        .arg(src);
        run(c);
        objects.push(obj.clone());
    }
    let lib = out.join("libqjsbundle.a");
    let _ = fs::remove_file(&lib);
    let mut a = Command::new(&ar);
    a.arg("crs").arg(&lib).args(&objects);
    run(a);

    println!("cargo:rustc-link-search=native={}", out.display());
    println!("cargo:rustc-link-lib=static=qjsbundle");
    println!("cargo:rustc-link-lib=m");

    let rev = tool_output(
        "git",
        &["-C", source.to_str().unwrap(), "rev-parse", "HEAD"],
    );
    assert!(
        rev.len() == 40 && rev.chars().all(|c| c.is_ascii_hexdigit()),
        "cannot establish the pinned source revision"
    );
    let quickjs = fs::read_to_string(vendor.join("VERSION")).unwrap_or_default();
    let rustc = env::var("RUSTC").unwrap_or_else(|_| "rustc".into());
    println!("cargo:rustc-env=SIM_UPSTREAM_REV={}", rev);
    println!("cargo:rustc-env=SIM_QUICKJS_VERSION={}", quickjs.trim());
    println!(
        "cargo:rustc-env=SIM_CC_VERSION={}",
        tool_output(&cc, &["--version"])
    );
    println!(
        "cargo:rustc-env=SIM_RUSTC_VERSION={}",
        tool_output(&rustc, &["--version"])
    );
}

use std::ffi::CString;
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::os::unix::fs::OpenOptionsExt;
use std::path::Path;

#[repr(C)]
struct Limits {
    deadline_ms: usize,
    heap_bytes: usize,
    stack_bytes: usize,
    max_source_bytes: usize,
    max_event_bytes: usize,
    max_config_bytes: usize,
    max_result_bytes: usize,
    max_result_depth: usize,
    max_actions: usize,
}
const MAX_MANIFEST_BYTES: usize = 32 * 1024;
const LIMITS: Limits = Limits {
    deadline_ms: 50,
    heap_bytes: 8 * 1024 * 1024,
    stack_bytes: 256 * 1024,
    max_source_bytes: 131072,
    max_event_bytes: 65536,
    max_config_bytes: 8192,
    max_result_bytes: 32768,
    max_result_depth: 32,
    max_actions: 2,
};
#[repr(C)]
struct QjsResult {
    status: i32,
    data: *mut u8,
    length: usize,
}
extern "C" {
    fn sim_open_flags() -> i32;
    fn sim_validate_json(bytes: *const u8, len: usize, object_required: i32, depth: i32) -> i32;
    fn qjs_cancel_token_new() -> *mut std::ffi::c_void;
    fn qjs_cancel_token_free(token: *mut std::ffi::c_void);
    fn qjs_run(
        token: *mut std::ffi::c_void,
        limits: *const Limits,
        source: *const u8,
        source_len: usize,
        hook: *const std::ffi::c_char,
        event: *const u8,
        event_len: usize,
        config: *const u8,
        config_len: usize,
    ) -> QjsResult;
    fn qjs_run_v2(
        token: *mut std::ffi::c_void,
        limits: *const Limits,
        source: *const u8,
        source_len: usize,
        hook: *const std::ffi::c_char,
        event: *const u8,
        event_len: usize,
        config: *const u8,
        config_len: usize,
        manifest: *const u8,
        manifest_len: usize,
    ) -> QjsResult;
    fn qjs_result_free(result: *mut QjsResult);
    fn sim_check_syntax(
        limits: *const Limits,
        source: *const u8,
        source_len: usize,
        diag: *mut std::ffi::c_char,
        diag_cap: usize,
    ) -> i32;
}
impl Drop for QjsResult {
    fn drop(&mut self) {
        unsafe { qjs_result_free(self) }
    }
}
struct Token(*mut std::ffi::c_void);
impl Drop for Token {
    fn drop(&mut self) {
        unsafe { qjs_cancel_token_free(self.0) }
    }
}

fn read_regular(path: &str, cap: usize) -> Result<Vec<u8>, String> {
    let file: File = OpenOptions::new()
        .read(true)
        .custom_flags(unsafe { sim_open_flags() })
        .open(Path::new(path))
        .map_err(|e| format!("cannot open {}: {}", path, e))?;
    let metadata = file.metadata().map_err(|e| e.to_string())?;
    if !metadata.is_file() || metadata.len() > cap as u64 {
        return Err(format!("invalid or oversized file: {}", path));
    }
    let mut bytes = Vec::new();
    file.take((cap + 1) as u64)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() > cap {
        return Err(format!("oversized file: {}", path));
    }
    Ok(bytes)
}

fn execute(args: &[String]) -> Result<i32, String> {
    if args.len() == 1 && args[0] == "--version" {
        println!(
            "interceptor-simulator {}\nupstream {}\nQuickJS {}\n{}\n{}",
            env!("CARGO_PKG_VERSION"),
            env!("SIM_UPSTREAM_REV"),
            env!("SIM_QUICKJS_VERSION"),
            env!("SIM_RUSTC_VERSION"),
            env!("SIM_CC_VERSION")
        );
        return Ok(0);
    }
    if args.is_empty() || (args.len() == 1 && matches!(args[0].as_str(), "--help" | "-h")) {
        println!("usage: interceptor-simulator check SOURCE.js\n       interceptor-simulator run SOURCE.js request.onEnter|request.onLeave|response.onEnter|response.onLeave EVENT.json CONFIG.json --manifest MANIFEST.json\n       interceptor-simulator run SOURCE.js onRequest|onResponse EVENT.json CONFIG.json (legacy v1)\n       interceptor-simulator --version\n\ncheck parses JavaScript without executing it. run prints action JSON only; no webhooks are sent.");
        return Ok(0);
    }
    match (args[0].as_str(), args.len()) {
        ("check", 2) => {
            let source = read_regular(&args[1], LIMITS.max_source_bytes)?;
            let mut diagnostic = [0u8; 2048];
            let status = unsafe {
                sim_check_syntax(
                    &LIMITS,
                    source.as_ptr(),
                    source.len(),
                    diagnostic.as_mut_ptr().cast(),
                    diagnostic.len(),
                )
            };
            if status == 0 {
                println!("Syntax OK");
            } else {
                let end = diagnostic
                    .iter()
                    .position(|b| *b == 0)
                    .unwrap_or(diagnostic.len());
                eprintln!(
                    "QuickJS status {}: {}",
                    status,
                    String::from_utf8_lossy(&diagnostic[..end])
                );
            }
            Ok(status)
        }
        ("run", 5) | ("run", 7) => {
            let v2 = args.len() == 7;
            if v2 && args[5] != "--manifest" {
                return Err("invalid arguments; use --help".into());
            }
            let allowed: &[&str] = if v2 {
                &[
                    "request.onEnter",
                    "request.onLeave",
                    "response.onEnter",
                    "response.onLeave",
                ]
            } else {
                &["onRequest", "onResponse"]
            };
            if !allowed.contains(&args[2].as_str()) {
                return Err(if v2 {
                    "hook must be request.onEnter, request.onLeave, response.onEnter or response.onLeave"
                } else {
                    "hook must be onRequest or onResponse"
                }
                .into());
            }
            let source = read_regular(&args[1], LIMITS.max_source_bytes)?;
            let event = read_regular(&args[3], LIMITS.max_event_bytes)?;
            let config = read_regular(&args[4], LIMITS.max_config_bytes)?;
            let manifest = if v2 {
                read_regular(&args[6], MAX_MANIFEST_BYTES)?
            } else {
                Vec::new()
            };
            for input in [&event, &config].into_iter().chain(v2.then_some(&manifest)) {
                if unsafe { sim_validate_json(input.as_ptr(), input.len(), 1, 64) } == 0 {
                    return Err("event, config and manifest must be strict JSON objects".into());
                }
            }
            let hook = CString::new(args[2].as_bytes()).map_err(|_| "invalid hook")?;
            let token = Token(unsafe { qjs_cancel_token_new() });
            if token.0.is_null() {
                return Ok(7);
            }
            let result = unsafe {
                if v2 {
                    qjs_run_v2(
                        token.0,
                        &LIMITS,
                        source.as_ptr(),
                        source.len(),
                        hook.as_ptr(),
                        event.as_ptr(),
                        event.len(),
                        config.as_ptr(),
                        config.len(),
                        manifest.as_ptr(),
                        manifest.len(),
                    )
                } else {
                    qjs_run(
                        token.0,
                        &LIMITS,
                        source.as_ptr(),
                        source.len(),
                        hook.as_ptr(),
                        event.as_ptr(),
                        event.len(),
                        config.as_ptr(),
                        config.len(),
                    )
                }
            };
            if result.status == 0 {
                if result.data.is_null() || result.length > LIMITS.max_result_bytes {
                    return Ok(7);
                }
                let data = unsafe { std::slice::from_raw_parts(result.data, result.length) };
                if unsafe {
                    sim_validate_json(data.as_ptr(), data.len(), 0, LIMITS.max_result_depth as i32)
                } == 0
                {
                    eprintln!("QuickJS status 5: invalid result JSON");
                    return Ok(5);
                }
                let mut output = std::io::stdout().lock();
                output
                    .write_all(data)
                    .and_then(|_| output.write_all(b"\n"))
                    .map_err(|e| e.to_string())?;
            } else {
                eprintln!("QuickJS status {}", result.status);
            }
            Ok(result.status)
        }
        _ => Err("invalid arguments; use --help".into()),
    }
}
fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let status = match execute(&args) {
        Ok(status) => status,
        Err(message) => {
            eprintln!("{}", message);
            4
        }
    };
    std::process::exit(status);
}

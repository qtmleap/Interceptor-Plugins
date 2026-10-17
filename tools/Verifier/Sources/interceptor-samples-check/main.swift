import AutomationCore
import AutomationRepository
import AutomationRuntime
import Foundation

// Public production APIs only: PluginPackage, RepositoryEnvelope, RepositoryClient, JavaScriptExecutor.

struct Fail: Error { let message: String }

let usage = """
usage: interceptor-samples-check samples ROOT DIRECTORY
       interceptor-samples-check verify-local ROOT DIRECTORY [--signed]
       interceptor-samples-check verify-live ROOT SEQUENCE
       interceptor-samples-check previous ROOT FILE

"""

let minimumRemainingLifetime: TimeInterval = 14 * 86_400

// MARK: - Files

/// Regular, non-symlink file no larger than `limit`.
func readRegular(_ path: String, limit: Int) throws -> Data {
    let fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
    guard fd >= 0 else { throw Fail(message: "cannot open \(path): \(String(cString: strerror(errno)))") }
    defer { close(fd) }
    var st = stat()
    guard fstat(fd, &st) == 0, (st.st_mode & S_IFMT) == S_IFREG else { throw Fail(message: "\(path): not a regular file") }
    guard st.st_size <= limit else { throw Fail(message: "\(path): larger than \(limit) bytes") }
    var out = Data(), buffer = [UInt8](repeating: 0, count: 16_384)
    while out.count <= limit {
        let n = read(fd, &buffer, buffer.count)
        if n < 0 { throw Fail(message: "cannot read \(path): \(String(cString: strerror(errno)))") }
        if n == 0 { break }
        out.append(contentsOf: buffer[0..<n])
    }
    guard out.count <= limit else { throw Fail(message: "\(path): larger than \(limit) bytes") }
    return out
}

func json(_ path: String, _ what: String) throws -> JSONValue {
    do { return try JSONValue(parsing: try readRegular(path, limit: 1_048_576)) }
    catch let error as Fail { throw error }
    catch { throw Fail(message: "\(what): invalid JSON (\(error))") }
}

func directoryNames(_ path: String, suffix: String) throws -> [String] {
    var st = stat()
    guard lstat(path, &st) == 0, (st.st_mode & S_IFMT) == S_IFDIR else { throw Fail(message: "\(path): not a real directory") }
    let names = try FileManager.default.contentsOfDirectory(atPath: path).sorted()
    return try names.map { name in
        guard name.hasSuffix(suffix), !name.hasPrefix(".") else { throw Fail(message: "unexpected entry \(name) in \(path)") }
        return String(name.dropLast(suffix.count))
    }
}

// MARK: - Configuration

struct Configuration {
    let id: UUID
    let url: RepositoryURL
    let fingerprint: String?
    let pluginIDs: Set<UUID>
}

func loadConfiguration(_ root: String) throws -> Configuration {
    guard let config = try json(root + "/repository-config.json", "repository-config.json").objectValue,
          let idText = config["id"]?.stringValue, let id = UUID(uuidString: idText),
          let urlText = config["repositoryURL"]?.stringValue else { throw Fail(message: "repository-config.json: invalid") }
    let url: RepositoryURL
    do { url = try RepositoryURL(parsing: urlText) } catch { throw Fail(message: "repository-config.json: invalid repositoryURL") }
    var fingerprint: String?
    switch config["publicKeyFingerprint"] {
    case .some(.string(let text)): fingerprint = text
    case .some(.null), .none: fingerprint = nil
    default: throw Fail(message: "repository-config.json: invalid publicKeyFingerprint")
    }
    var ids = Set<UUID>()
    for name in try directoryNames(root + "/manifests", suffix: ".json") {
        guard let manifest = try json(root + "/manifests/\(name).json", "manifests/\(name).json").objectValue,
              let text = manifest["id"]?.stringValue, let pluginID = UUID(uuidString: text), ids.insert(pluginID).inserted else {
            throw Fail(message: "manifests/\(name).json: missing or duplicate id")
        }
    }
    guard !ids.isEmpty else { throw Fail(message: "no manifests") }
    return Configuration(id: id, url: url, fingerprint: fingerprint, pluginIDs: ids)
}

/// Identity, signature and plugin-set checks shared by verify-local / verify-live / previous.
func checkIdentity(_ snapshot: VerifiedSnapshot, _ config: Configuration, requireSigned: Bool) throws {
    guard snapshot.index.id == config.id else { throw Fail(message: "repository id does not match repository-config.json") }
    switch snapshot.signature {
    case .signed(let key):
        guard let expected = config.fingerprint else { throw Fail(message: "signed feed but no publicKeyFingerprint configured") }
        guard key.hex == expected else { throw Fail(message: "signing key fingerprint \(key.hex) does not match the configured fingerprint") }
    case .unsigned:
        if requireSigned { throw Fail(message: "feed is unsigned but a signature is required") }
    }
}

func checkPluginSet(_ snapshot: VerifiedSnapshot, _ config: Configuration) throws {
    guard Set(snapshot.index.plugins.map(\.id)) == config.pluginIDs, snapshot.index.plugins.count == config.pluginIDs.count else {
        throw Fail(message: "feed plugin ids do not match manifests/")
    }
}

func summary(_ snapshot: VerifiedSnapshot) throws -> String {
    var object: [String: JSONValue] = [
        "sequence": .integer(snapshot.index.sequence),
        "repositoryId": .string(snapshot.index.id.uuidString),
        "plugins": .integer(Int64(snapshot.index.plugins.count)),
        "signed": .bool({ if case .signed = snapshot.signature { return true } else { return false } }()),
    ]
    if case .signed(let key) = snapshot.signature { object["fingerprint"] = .string(key.hex) } else { object["fingerprint"] = .null }
    return try JSONValue.object(object).jsonString()
}

// MARK: - samples

func runSamples(root: String, directory: String) async throws {
    let config = try loadConfiguration(root)
    let configJSON = try readRegular(root + "/fixtures/config.json", limit: JavaScriptLimits.maxConfigBytes)

    var packages = [String: PluginPackage]()
    for name in try directoryNames(directory + "/plugins", suffix: ".json") {
        let package: PluginPackage
        do { package = try PluginPackage.validate(try readRegular(directory + "/plugins/\(name).json", limit: Limits.package)) }
        catch let error as Fail { throw error }
        catch { throw Fail(message: "plugins/\(name).json: invalid package (\(error))") }
        let script = try readRegular(root + "/scripts/\(name).js", limit: Limits.source)
        guard package.source == String(decoding: script, as: UTF8.self) else { throw Fail(message: "plugins/\(name).json: source differs from scripts/\(name).js") }
        packages[name] = package
    }
    guard Set(packages.values.map(\.manifest.id)) == config.pluginIDs else { throw Fail(message: "packages do not match manifests/") }

    guard let cases = try json(root + "/fixtures/cases.json", "fixtures/cases.json").arrayValue, !cases.isEmpty else {
        throw Fail(message: "fixtures/cases.json: expected a non-empty array")
    }
    let executor = JavaScriptExecutor()
    var covered = Set<String>(), failures = [String]()
    for (index, entry) in cases.enumerated() {
        guard let fields = entry.objectValue, let name = fields["name"]?.stringValue,
              let plugin = fields["plugin"]?.stringValue, let hookName = fields["hook"]?.stringValue,
              let hook = JavaScriptHook(rawValue: hookName), let event = fields["event"], event.objectValue != nil,
              let package = packages[plugin] else { throw Fail(message: "fixtures/cases.json[\(index)]: invalid case") }
        let hasExpected = fields["expected"] != nil, hasError = fields["expectError"] != nil
        guard hasExpected != hasError, Set(fields.keys).isSubset(of: ["name", "plugin", "hook", "event", "expected", "expectError"]) else {
            throw Fail(message: "fixtures/cases.json[\(index)] \(name): needs exactly one of expected / expectError")
        }
        covered.insert(plugin)
        do {
            let output = try await executor.run(source: package.source, hook: hook, eventJSON: try event.data(), configJSON: configJSON)
            if hasError { failures.append("\(name): expected scriptError, got result \(String(decoding: output, as: UTF8.self))") }
            else if try JSONValue(parsing: output) != fields["expected"]! {
                failures.append("\(name): expected \(try fields["expected"]!.jsonString()), got \(String(decoding: output, as: UTF8.self))")
            }
        } catch let error as JavaScriptExecutionError {
            if fields["expectError"]?.stringValue == "scriptError", error == .scriptError { continue }
            failures.append("\(name): unexpected \(error)")
        }
    }
    guard covered == Set(packages.keys) else { throw Fail(message: "fixtures/cases.json does not cover every package") }
    if !failures.isEmpty { throw Fail(message: "sample cases failed:\n  " + failures.joined(separator: "\n  ")) }
    print("samples ok: \(cases.count) cases, \(packages.count) packages")
}

// MARK: - verify-local

func runVerifyLocal(root: String, directory: String, signed: Bool) throws {
    let config = try loadConfiguration(root)
    if signed, config.fingerprint == nil { throw Fail(message: "--signed requires publicKeyFingerprint in repository-config.json") }
    let envelope = try readRegular(directory + "/repository.json", limit: Limits.envelope)
    let snapshot: VerifiedSnapshot
    do { snapshot = try RepositoryEnvelope.verify(envelope: envelope, url: config.url, now: Date()) }
    catch { throw Fail(message: "repository.json rejected: \(error)") }
    try checkIdentity(snapshot, config, requireSigned: signed)
    try checkPluginSet(snapshot, config)

    let onDisk = try directoryNames(directory + "/plugins", suffix: ".json").map { "plugins/\($0).json" }
    guard Set(onDisk) == Set(snapshot.index.plugins.map(\.packagePath)) else { throw Fail(message: "plugins/ does not match the feed") }
    for entry in snapshot.index.plugins {
        let bytes = try readRegular(directory + "/" + entry.packagePath, limit: Limits.package)
        do { _ = try PluginPackage.validate(bytes, against: entry) }
        catch { throw Fail(message: "\(entry.packagePath) rejected: \(error)") }
    }
    print(try summary(snapshot))
}

// MARK: - verify-live

func runVerifyLive(root: String, sequence: Int64) async throws {
    let config = try loadConfiguration(root)
    guard config.fingerprint != nil else { throw Fail(message: "verify-live requires publicKeyFingerprint in repository-config.json") }
    let client = RepositoryClient()
    let now = Date()
    let snapshot: VerifiedSnapshot
    do { snapshot = try await client.preview(url: config.url, now: now) }
    catch { throw Fail(message: "live feed rejected: \(error)") }
    try checkIdentity(snapshot, config, requireSigned: true)
    try checkPluginSet(snapshot, config)
    guard snapshot.index.sequence == sequence else { throw Fail(message: "live sequence \(snapshot.index.sequence) is not the expected \(sequence)") }
    guard snapshot.index.expiresAt.timeIntervalSince(now) >= minimumRemainingLifetime else { throw Fail(message: "live feed expires in less than 14 days") }
    for entry in snapshot.index.plugins {
        do { _ = try await client.fetchPackage(entry: entry, from: snapshot) }
        catch { throw Fail(message: "live package \(entry.packagePath) rejected: \(error)") }
    }
    print(try summary(snapshot))
}

// MARK: - previous

func parseIssuedAt(_ text: String) -> Date? {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    return formatter.date(from: text)
}

func runPrevious(root: String, file: String) throws {
    let config = try loadConfiguration(root)
    guard config.fingerprint != nil else { throw Fail(message: "previous requires publicKeyFingerprint in repository-config.json") }
    let envelope = try readRegular(file, limit: Limits.envelope)
    // Untrusted pre-parse, used ONLY to choose the verification time; every trusted value comes from the snapshot.
    guard let top = (try? JSONValue(parsing: envelope))?.objectValue, let encoded = top["payload"]?.stringValue,
          let payload = Data(base64Encoded: encoded), let index = (try? JSONValue(parsing: payload))?.objectValue,
          let issuedText = index["issuedAt"]?.stringValue, let issuedAt = parseIssuedAt(issuedText) else {
        throw Fail(message: "previous feed: cannot read issuedAt")
    }
    let now = Date()
    guard issuedAt <= now.addingTimeInterval(Limits.clockSkew) else { throw Fail(message: "previous feed was issued in the future") }
    let snapshot: VerifiedSnapshot
    do { snapshot = try RepositoryEnvelope.verify(envelope: envelope, url: config.url, now: issuedAt) }
    catch { throw Fail(message: "previous feed rejected: \(error)") }
    try checkIdentity(snapshot, config, requireSigned: true)
    print(snapshot.index.sequence)
}

// MARK: - Entry point

func run(_ args: [String]) async throws {
    switch (args.first, args.count) {
    case ("samples", 3): try await runSamples(root: args[1], directory: args[2])
    case ("verify-local", 3): try runVerifyLocal(root: args[1], directory: args[2], signed: false)
    case ("verify-local", 4) where args[3] == "--signed": try runVerifyLocal(root: args[1], directory: args[2], signed: true)
    case ("verify-live", 3):
        guard let sequence = Int64(args[2]), (1...Limits.maxSequence).contains(sequence) else { throw Fail(message: "SEQUENCE must be 1...\(Limits.maxSequence)") }
        try await runVerifyLive(root: args[1], sequence: sequence)
    case ("previous", 3): try runPrevious(root: args[1], file: args[2])
    default: throw Fail(message: "unknown or incomplete command\n" + usage)
    }
}

do { try await run(Array(CommandLine.arguments.dropFirst())) } catch {
    let text = (error as? Fail)?.message ?? "\(error)"
    FileHandle.standardError.write(Data("error: \(text)\n".utf8))
    exit(1)
}

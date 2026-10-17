// Test-only authentic expired/future metadata, signed with the temporary test key.
import CryptoKit
import Foundation

enum FixtureFailure: Error { case invalidInput }

do {
    let arguments = Array(CommandLine.arguments.dropFirst())
    guard arguments.count == 4, ["expired", "future"].contains(arguments[3]),
          var envelope = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: arguments[0]))) as? [String: Any],
          let encoded = envelope["payload"] as? String, let bytes = Data(base64Encoded: encoded),
          var index = try JSONSerialization.jsonObject(with: bytes) as? [String: Any],
          var signature = envelope["signature"] as? [String: Any] else { throw FixtureFailure.invalidInput }
    let now = Date()
    let issued = arguments[3] == "expired" ? now.addingTimeInterval(-31 * 86_400) : now.addingTimeInterval(600)
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    index["issuedAt"] = formatter.string(from: issued)
    index["expiresAt"] = formatter.string(from: issued.addingTimeInterval(30 * 86_400))
    let payload = try JSONSerialization.data(withJSONObject: index, options: [.sortedKeys])
    let key = try Curve25519.Signing.PrivateKey(rawRepresentation: Data(contentsOf: URL(fileURLWithPath: arguments[1])))
    signature["value"] = try key.signature(for: Data("InterceptorRepository/v1".utf8) + Data([0]) + payload).base64EncodedString()
    envelope["payload"] = payload.base64EncodedString()
    envelope["signature"] = signature
    try JSONSerialization.data(withJSONObject: envelope, options: [.sortedKeys]).write(to: URL(fileURLWithPath: arguments[2]), options: .atomic)
} catch {
    FileHandle.standardError.write(Data("history fixture generation failed\n".utf8))
    exit(1)
}

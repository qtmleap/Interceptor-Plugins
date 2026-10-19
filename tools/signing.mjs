// Ed25519 primitives for tools/repository_tool.py, nothing else.
//
// Protocol (binary stdin, hex stdout, no secrets ever on argv or in output):
//   public  stdin = seed(32)                          -> raw public key, hex
//   sign    stdin = seed(32) || message               -> signature(64), hex
//   verify  stdin = publicKey(32) || signature(64) || message -> "1" or "0"
// Any malformed input exits 2 with a generic message that never echoes input bytes.
import { createPrivateKey, createPublicKey, sign, verify } from "node:crypto";
import { readFileSync } from "node:fs";

// Fixed DER prefixes that wrap a raw Ed25519 seed (PKCS#8) or public key (SPKI).
const PKCS8_PREFIX = Buffer.from("302e020100300506032b657004220420", "hex");
const SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex");
const SEED_BYTES = 32;
const SIGNATURE_BYTES = 64;

const fail = () => {
  process.stderr.write("signing: invalid input\n");
  process.exit(2);
};

const privateKey = (seed) => createPrivateKey({ key: Buffer.concat([PKCS8_PREFIX, seed]), format: "der", type: "pkcs8" });
const publicKey = (raw) => createPublicKey({ key: Buffer.concat([SPKI_PREFIX, raw]), format: "der", type: "spki" });
const rawPublic = (seed) => createPublicKey(privateKey(seed)).export({ format: "der", type: "spki" }).subarray(SPKI_PREFIX.length);

const commands = {
  public: (input) => {
    if (input.length !== SEED_BYTES) fail();
    return rawPublic(input).toString("hex");
  },
  sign: (input) => {
    if (input.length < SEED_BYTES) fail();
    const seed = input.subarray(0, SEED_BYTES);
    return sign(null, input.subarray(SEED_BYTES), privateKey(seed)).toString("hex");
  },
  verify: (input) => {
    if (input.length < SEED_BYTES + SIGNATURE_BYTES) fail();
    const key = publicKey(input.subarray(0, SEED_BYTES));
    const signature = input.subarray(SEED_BYTES, SEED_BYTES + SIGNATURE_BYTES);
    return verify(null, input.subarray(SEED_BYTES + SIGNATURE_BYTES), key, signature) ? "1" : "0";
  },
};

const command = Object.hasOwn(commands, process.argv[2] ?? "") ? commands[process.argv[2]] : fail();
try {
  process.stdout.write(command(readFileSync(0)) + "\n");
} catch {
  fail();
}

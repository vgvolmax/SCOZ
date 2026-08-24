import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";

if (!globalThis.crypto) Object.defineProperty(globalThis, "crypto", { value: webcrypto });
await import("../frontend/assets/js/keystore.js");

const keystore = globalThis.ScozKeystore;
assert.ok(Object.isFrozen(keystore));
assert.deepEqual(Object.keys(keystore), [
  "encryptMpstatsCredentials",
  "decryptMpstatsCredentials",
  "serializeEnvelope",
  "parseEnvelope",
  "downloadEnvelope",
]);

async function rejectsCode(action, code) {
  await assert.rejects(action, (error) => error && error.code === code);
}

const token = "секретный-token-🔐";
const password = "  пароль é  ";
const envelope = await keystore.encryptMpstatsCredentials({ token }, password);
assert.deepEqual(await keystore.decryptMpstatsCredentials(envelope, password), { token });
await rejectsCode(
  () => keystore.decryptMpstatsCredentials(envelope, password.trim()),
  "KEYSTORE_DECRYPT_FAILED",
);

const second = await keystore.encryptMpstatsCredentials({ token }, password);
assert.notEqual(second.kdf.salt, envelope.kdf.salt);
assert.notEqual(second.cipher.iv, envelope.cipher.iv);
assert.notEqual(second.ciphertext, envelope.ciphertext);

assert.deepEqual(Object.keys(envelope), ["format", "version", "kdf", "cipher", "ciphertext"]);
assert.deepEqual(Object.keys(envelope.kdf), ["name", "hash", "iterations", "salt"]);
assert.deepEqual(Object.keys(envelope.cipher), ["name", "key_length", "iv", "tag_length"]);
assert.equal(envelope.format, "scoz-credentials-keystore");
assert.equal(envelope.version, 1);
assert.deepEqual(envelope.kdf, {
  name: "PBKDF2", hash: "SHA-256", iterations: 600000, salt: envelope.kdf.salt,
});
assert.deepEqual(envelope.cipher, {
  name: "AES-GCM", key_length: 256, iv: envelope.cipher.iv, tag_length: 128,
});
assert.match(envelope.kdf.salt, /^[A-Za-z0-9+/]{22}==$/);
assert.match(envelope.cipher.iv, /^[A-Za-z0-9+/]{16}$/);
assert.ok(!keystore.serializeEnvelope(envelope).includes(token));
assert.deepEqual(keystore.parseEnvelope(keystore.serializeEnvelope(envelope)), envelope);
const reordered = {
  ciphertext: envelope.ciphertext,
  cipher: envelope.cipher,
  kdf: envelope.kdf,
  version: envelope.version,
  format: envelope.format,
};
assert.equal(keystore.serializeEnvelope(reordered), JSON.stringify(envelope));

const corrupted = structuredClone(envelope);
corrupted.ciphertext = `${corrupted.ciphertext[0] === "A" ? "B" : "A"}${corrupted.ciphertext.slice(1)}`;
await rejectsCode(
  () => keystore.decryptMpstatsCredentials(corrupted, password),
  "KEYSTORE_DECRYPT_FAILED",
);

assert.throws(() => keystore.parseEnvelope("[]"), { code: "INVALID_KEYSTORE_ENVELOPE" });
assert.throws(
  () => keystore.parseEnvelope(JSON.stringify({ ...envelope, format: "other" })),
  { code: "UNSUPPORTED_KEYSTORE_FORMAT" },
);
assert.throws(
  () => keystore.parseEnvelope(JSON.stringify({ ...envelope, version: 2 })),
  { code: "UNSUPPORTED_KEYSTORE_VERSION" },
);
for (const invalid of [
  { ...envelope, extra: true },
  { ...envelope, version: 1.0, ciphertext: "AA==" },
  { ...envelope, kdf: { ...envelope.kdf, salt: envelope.kdf.salt.replace(/==$/, "") } },
  { ...envelope, cipher: { ...envelope.cipher, iv: ` ${envelope.cipher.iv}` } },
]) {
  assert.throws(
    () => keystore.parseEnvelope(JSON.stringify(invalid)),
    { code: "INVALID_KEYSTORE_ENVELOPE" },
  );
}
await rejectsCode(() => keystore.encryptMpstatsCredentials({ token }, ""), "INVALID_KEYSTORE_ENVELOPE");
await rejectsCode(() => keystore.encryptMpstatsCredentials({ token: "" }, password), "INVALID_KEYSTORE_ENVELOPE");

console.log("keystore contract: PASS");

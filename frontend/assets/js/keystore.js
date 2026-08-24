(function () {
  "use strict";

  const FORMAT = "scoz-credentials-keystore";
  const VERSION = 1;
  const encoder = new TextEncoder();
  const decoder = new TextDecoder("utf-8", { fatal: true });

  function failure(code) {
    const error = new Error(code);
    error.code = code;
    return error;
  }

  function exactKeys(value, keys) {
    return value !== null && typeof value === "object" && !Array.isArray(value)
      && Object.keys(value).length === keys.length
      && keys.every((key) => Object.prototype.hasOwnProperty.call(value, key));
  }

  function encodeBase64(bytes) {
    let binary = "";
    for (const byte of bytes) binary += String.fromCharCode(byte);
    return btoa(binary);
  }

  function decodeBase64(value) {
    if (typeof value !== "string" || value.length === 0
        || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) {
      throw failure("INVALID_KEYSTORE_ENVELOPE");
    }
    try {
      const binary = atob(value);
      const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
      if (encodeBase64(bytes) !== value) throw failure("INVALID_KEYSTORE_ENVELOPE");
      return bytes;
    } catch (error) {
      if (error && error.code === "INVALID_KEYSTORE_ENVELOPE") throw error;
      throw failure("INVALID_KEYSTORE_ENVELOPE");
    }
  }

  function validateEnvelope(envelope) {
    if (!exactKeys(envelope, ["format", "version", "kdf", "cipher", "ciphertext"])) {
      throw failure("INVALID_KEYSTORE_ENVELOPE");
    }
    if (typeof envelope.format !== "string") throw failure("INVALID_KEYSTORE_ENVELOPE");
    if (envelope.format !== FORMAT) throw failure("UNSUPPORTED_KEYSTORE_FORMAT");
    if (!Number.isInteger(envelope.version)) throw failure("INVALID_KEYSTORE_ENVELOPE");
    if (envelope.version !== VERSION) throw failure("UNSUPPORTED_KEYSTORE_VERSION");
    if (!exactKeys(envelope.kdf, ["name", "hash", "iterations", "salt"])
        || envelope.kdf.name !== "PBKDF2" || envelope.kdf.hash !== "SHA-256"
        || envelope.kdf.iterations !== 600000
        || !exactKeys(envelope.cipher, ["name", "key_length", "iv", "tag_length"])
        || envelope.cipher.name !== "AES-GCM" || envelope.cipher.key_length !== 256
        || envelope.cipher.tag_length !== 128) {
      throw failure("INVALID_KEYSTORE_ENVELOPE");
    }
    const salt = decodeBase64(envelope.kdf.salt);
    const iv = decodeBase64(envelope.cipher.iv);
    const ciphertext = decodeBase64(envelope.ciphertext);
    if (salt.length !== 16 || iv.length !== 12 || ciphertext.length < 17) {
      throw failure("INVALID_KEYSTORE_ENVELOPE");
    }
    return { salt, iv, ciphertext };
  }

  function canonicalEnvelope(envelope) {
    return {
      format: envelope.format,
      version: envelope.version,
      kdf: {
        name: envelope.kdf.name,
        hash: envelope.kdf.hash,
        iterations: envelope.kdf.iterations,
        salt: envelope.kdf.salt,
      },
      cipher: {
        name: envelope.cipher.name,
        key_length: envelope.cipher.key_length,
        iv: envelope.cipher.iv,
        tag_length: envelope.cipher.tag_length,
      },
      ciphertext: envelope.ciphertext,
    };
  }

  function validatePassword(password) {
    if (typeof password !== "string" || password.length === 0) {
      throw failure("INVALID_KEYSTORE_ENVELOPE");
    }
  }

  async function deriveKey(password, salt) {
    const material = await crypto.subtle.importKey(
      "raw", encoder.encode(password), "PBKDF2", false, ["deriveKey"],
    );
    return crypto.subtle.deriveKey(
      { name: "PBKDF2", hash: "SHA-256", iterations: 600000, salt },
      material,
      { name: "AES-GCM", length: 256 },
      false,
      ["encrypt", "decrypt"],
    );
  }

  async function encryptMpstatsCredentials(credentials, password) {
    validatePassword(password);
    if (!exactKeys(credentials, ["token"])
        || typeof credentials.token !== "string" || credentials.token.length === 0) {
      throw failure("INVALID_KEYSTORE_ENVELOPE");
    }
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await deriveKey(password, salt);
    const payload = encoder.encode(JSON.stringify({
      version: 1,
      sources: { mpstats: { token: credentials.token } },
    }));
    const ciphertext = new Uint8Array(await crypto.subtle.encrypt(
      { name: "AES-GCM", iv, tagLength: 128 }, key, payload,
    ));
    return {
      format: FORMAT,
      version: VERSION,
      kdf: { name: "PBKDF2", hash: "SHA-256", iterations: 600000, salt: encodeBase64(salt) },
      cipher: { name: "AES-GCM", key_length: 256, iv: encodeBase64(iv), tag_length: 128 },
      ciphertext: encodeBase64(ciphertext),
    };
  }

  async function decryptMpstatsCredentials(envelope, password) {
    validatePassword(password);
    const { salt, iv, ciphertext } = validateEnvelope(envelope);
    try {
      const key = await deriveKey(password, salt);
      const plaintext = await crypto.subtle.decrypt(
        { name: "AES-GCM", iv, tagLength: 128 }, key, ciphertext,
      );
      const payload = JSON.parse(decoder.decode(plaintext));
      if (!exactKeys(payload, ["version", "sources"]) || payload.version !== 1
          || !exactKeys(payload.sources, ["mpstats"])
          || !exactKeys(payload.sources.mpstats, ["token"])
          || typeof payload.sources.mpstats.token !== "string"
          || payload.sources.mpstats.token.length === 0) {
        throw failure("KEYSTORE_DECRYPT_FAILED");
      }
      return { token: payload.sources.mpstats.token };
    } catch (_) {
      throw failure("KEYSTORE_DECRYPT_FAILED");
    }
  }

  function serializeEnvelope(envelope) {
    validateEnvelope(envelope);
    return JSON.stringify(canonicalEnvelope(envelope));
  }

  function parseEnvelope(jsonText) {
    let envelope;
    try {
      envelope = JSON.parse(jsonText);
    } catch (_) {
      throw failure("INVALID_KEYSTORE_ENVELOPE");
    }
    validateEnvelope(envelope);
    return canonicalEnvelope(envelope);
  }

  function downloadEnvelope(envelope) {
    const blob = new Blob([serializeEnvelope(envelope)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "scoz_credentials.enc.json";
    document.body.appendChild(anchor);
    try {
      anchor.click();
    } finally {
      anchor.remove();
      URL.revokeObjectURL(url);
    }
  }

  globalThis.ScozKeystore = Object.freeze({
    encryptMpstatsCredentials,
    decryptMpstatsCredentials,
    serializeEnvelope,
    parseEnvelope,
    downloadEnvelope,
  });
}());

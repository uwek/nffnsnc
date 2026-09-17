// NFFNSNC Frontend: entschlüsselt nffnsnc.enc vollständig im Browser.
//
// Container-Format (muss zu nffformat.py passen):
//   Magic "NFF1" (4) | Version (1) | Iterationen (4, big-endian)
//   | Salt (16) | Nonce (12) | AES-256-GCM-Ciphertext + Tag
// Der 37-Byte-Header ist Associated Data (AAD) der GCM-Entschlüsselung.
(function () {
  'use strict';

  var MAGIC = [0x4e, 0x46, 0x46, 0x31]; // "NFF1"
  var VERSION = 1;
  var HEADER_LEN = 37;
  var MIN_ITERATIONS = 100000;
  var MAX_ITERATIONS = 50000000;
  var DOWNLOAD_NAME = 'Notfall_Dokument_Entschluesselt.pdf';

  var form = document.getElementById('decryptForm');
  var passwordInput = document.getElementById('passwordInput');
  var toggleBtn = document.getElementById('togglePassword');
  var statusEl = document.getElementById('status');
  var buttons = form.querySelectorAll('button[type="submit"]');
  var offlineLink = document.getElementById('offlineLink');
  var lastAction = 'view';
  var busy = false;

  function setStatus(message, cls) {
    statusEl.className = cls || '';
    statusEl.textContent = message;
  }

  function setBusy(state) {
    busy = state;
    for (var i = 0; i < buttons.length; i++) buttons[i].disabled = state;
  }

  // Identisch zu nffformat.normalize_password: NFKC + trim.
  function normalizePassword(raw) {
    var s = raw;
    if (typeof s.normalize === 'function') s = s.normalize('NFKC');
    return s.trim();
  }

  function getSubtle() {
    var c = window.crypto;
    if (!c || !c.subtle) {
      throw new Error('Der Browser stellt keine Verschlüsselungsfunktionen bereit. ' +
        'Bitte die Seite über https:// öffnen (nicht über http://) oder einen aktuellen Browser verwenden.');
    }
    return c.subtle;
  }

  function base64ToBuffer(b64) {
    var bin = atob(b64);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes.buffer;
  }

  async function loadContainer() {
    if (typeof window.NFFNSNC_EMBEDDED === 'string') {
      return base64ToBuffer(window.NFFNSNC_EMBEDDED);
    }
    var response;
    try {
      response = await fetch('nffnsnc.enc', { cache: 'no-cache' });
    } catch (e) {
      throw new Error('Verschlüsselte Datei konnte nicht geladen werden (keine Verbindung?).');
    }
    if (!response.ok) {
      throw new Error('Verschlüsselte Datei konnte nicht geladen werden (HTTP ' + response.status + ').');
    }
    return response.arrayBuffer();
  }

  function parseContainer(buffer) {
    if (buffer.byteLength < HEADER_LEN + 16) throw new Error('Datei zu kurz oder beschädigt.');
    var bytes = new Uint8Array(buffer);
    for (var i = 0; i < MAGIC.length; i++) {
      if (bytes[i] !== MAGIC[i]) throw new Error('Unbekanntes Dateiformat.');
    }
    if (bytes[4] !== VERSION) throw new Error('Nicht unterstützte Formatversion ' + bytes[4] + '.');
    var iterations = new DataView(buffer).getUint32(5, false);
    if (iterations < MIN_ITERATIONS || iterations > MAX_ITERATIONS) {
      throw new Error('Unplausible Schlüsselparameter in der Datei.');
    }
    return {
      header: buffer.slice(0, HEADER_LEN),
      iterations: iterations,
      salt: buffer.slice(9, 25),
      nonce: buffer.slice(25, 37),
      ciphertext: buffer.slice(HEADER_LEN)
    };
  }

  async function decrypt(password, container) {
    var subtle = getSubtle();
    var passwordKey = await subtle.importKey(
      'raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']);
    var aesKey = await subtle.deriveKey(
      { name: 'PBKDF2', salt: container.salt, iterations: container.iterations, hash: 'SHA-256' },
      passwordKey,
      { name: 'AES-GCM', length: 256 },
      false,
      ['decrypt']);
    try {
      return await subtle.decrypt(
        { name: 'AES-GCM', iv: container.nonce, additionalData: container.header },
        aesKey, container.ciphertext);
    } catch (e) {
      throw new Error('Entschlüsselung fehlgeschlagen. Die Passphrase ist vermutlich falsch. ' +
        'Bitte Groß-/Kleinschreibung und Leerzeichen prüfen (Button "Anzeigen" hilft beim Vergleich).');
    }
  }

  async function getDecryptedBlob() {
    var password = normalizePassword(passwordInput.value);
    if (!password) throw new Error('Bitte die Passphrase eingeben.');
    getSubtle(); // früh prüfen, bevor ein Fenster geöffnet wird
    setStatus('Datei wird geladen...', 'info');
    var container = parseContainer(await loadContainer());
    setStatus('Schlüssel wird berechnet, das kann einige Sekunden dauern...', 'info');
    var plain = await decrypt(password, container);
    return new Blob([plain], { type: 'application/pdf' });
  }

  var blobUrls = [];
  function trackUrl(url) { blobUrls.push(url); return url; }
  window.addEventListener('pagehide', function () {
    blobUrls.forEach(function (u) { try { URL.revokeObjectURL(u); } catch (e) {} });
  });

  async function viewPdf() {
    // Fenster synchron im Klick-Handler öffnen, sonst blockieren Safari/iOS
    // das Popup nach dem asynchronen await.
    var win = null;
    try {
      win = window.open('', '_blank');
      if (win && win.document) {
        win.document.write('<!DOCTYPE html><title>Notfall-Dokument</title>' +
          '<p style="font-family:sans-serif;padding:2rem">Dokument wird entschlüsselt...</p>');
        win.document.close();
      }
    } catch (e) { win = null; }

    try {
      var blob = await getDecryptedBlob();
      var url = trackUrl(URL.createObjectURL(blob));
      if (win && !win.closed) {
        win.location.href = url;
        setStatus('Entschlüsselung erfolgreich. Das PDF wurde in einem neuen Tab geöffnet.', 'success');
      } else {
        // Popup blockiert: im aktuellen Tab anzeigen.
        setStatus('Entschlüsselung erfolgreich. Das PDF wird angezeigt.', 'success');
        window.location.href = url;
      }
    } catch (err) {
      if (win && !win.closed) { try { win.close(); } catch (e) {} }
      throw err;
    }
  }

  async function downloadPdf() {
    var blob = await getDecryptedBlob();
    var url = trackUrl(URL.createObjectURL(blob));
    var a = document.createElement('a');
    a.href = url;
    a.download = DOWNLOAD_NAME;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { document.body.removeChild(a); }, 100);
    setStatus('Entschlüsselung erfolgreich. Der Download wurde gestartet (' + DOWNLOAD_NAME + ').', 'success');
  }

  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener('click', function (ev) {
      lastAction = ev.currentTarget.getAttribute('data-action') || 'view';
    });
  }

  form.addEventListener('submit', async function (ev) {
    ev.preventDefault();
    if (busy) return;
    var action = (ev.submitter && ev.submitter.getAttribute('data-action')) || lastAction;
    setBusy(true);
    try {
      if (action === 'download') await downloadPdf(); else await viewPdf();
    } catch (err) {
      setStatus(err.message || 'Entschlüsselung fehlgeschlagen.', 'error');
    } finally {
      setBusy(false);
    }
  });

  toggleBtn.addEventListener('click', function () {
    var show = passwordInput.type === 'password';
    passwordInput.type = show ? 'text' : 'password';
    toggleBtn.setAttribute('aria-pressed', show ? 'true' : 'false');
    toggleBtn.textContent = show ? 'Verbergen' : 'Anzeigen';
    passwordInput.focus();
  });

  // In der Offline-Kopie ist der Link auf sich selbst sinnlos.
  if (typeof window.NFFNSNC_EMBEDDED === 'string' && offlineLink) {
    offlineLink.parentNode.hidden = true;
  }

  try { getSubtle(); } catch (e) { setStatus(e.message, 'error'); }
})();

(function ensureAdoptedStyleSheets(doc) {
  if (!doc) return;

  const nativeSheets = doc.adoptedStyleSheets;
  if (nativeSheets && typeof nativeSheets.filter === 'function') return;

  const buffer = Array.isArray(nativeSheets)
    ? nativeSheets.slice()
    : Array.from(nativeSheets || []);

  try {
    Object.defineProperty(doc, 'adoptedStyleSheets', {
      configurable: true,
      enumerable: true,
      get() {
        return buffer;
      },
      set(value) {
        const next = Array.isArray(value) ? value : Array.from(value || []);
        buffer.splice(0, buffer.length, ...next);
      }
    });
  } catch (err) {
    /* noop - fallback below will still attach a filter function */
  }

  const sheets = doc.adoptedStyleSheets || buffer;
  if (sheets && typeof sheets.filter !== 'function') {
    try {
      sheets.filter = Array.prototype.filter.bind(sheets);
    } catch (err) {
      try {
        Object.setPrototypeOf(sheets, Array.prototype);
      } catch (err) {
        // ignore prototype failure
      }
      sheets.filter = Array.prototype.filter.bind(Array.from(buffer));
    }
  }
})(document);

(function ensureAdoptedStyleSheets(doc) {
  if (!doc || !('adoptedStyleSheets' in doc)) return;

  const sheets = doc.adoptedStyleSheets;
  if (Array.isArray(sheets) && typeof sheets.filter === 'function') return;

  try {
    const buffer = Array.from(sheets || []);
    Object.defineProperty(doc, 'adoptedStyleSheets', {
      configurable: true,
      enumerable: true,
      get() {
        return buffer;
      },
      set(value) {
        if (Array.isArray(value)) {
          buffer.splice(0, buffer.length, ...value);
        } else if (value && typeof value.length === 'number') {
          buffer.splice(0, buffer.length, ...Array.from(value));
        }
      }
    });
  } catch (err) {
    if (sheets && typeof sheets.filter !== 'function') {
      sheets.filter = Array.prototype.filter.bind(Array.from(sheets));
    }
  }
})(document);

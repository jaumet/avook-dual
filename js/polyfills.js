(function ensureAdoptedStyleSheets(doc) {
  if (!doc) return;

  const normalize = (value, fallbackBuffer) => {
    const arrayValue = Array.isArray(value) ? value : Array.from(value || fallbackBuffer || []);
    if (typeof arrayValue.filter !== 'function') {
      const filterFn = Array.prototype.filter.bind(arrayValue);
      try {
        Object.defineProperty(arrayValue, 'filter', { value: filterFn, configurable: true, writable: true });
      } catch (err) {
        try {
          arrayValue.filter = filterFn;
        } catch (err) {
          /* ignore assignment failure */
        }
      }
    }
    return arrayValue;
  };

  const nativeSheets = doc.adoptedStyleSheets;
  const buffer = normalize(nativeSheets);

  if (nativeSheets && typeof nativeSheets.filter === 'function') return;

  const applyDescriptor = () => {
    try {
      Object.defineProperty(doc, 'adoptedStyleSheets', {
        configurable: true,
        enumerable: true,
        get() {
          return buffer;
        },
        set(value) {
          const next = normalize(value, buffer);
          buffer.splice(0, buffer.length, ...next);
        }
      });
      return typeof doc.adoptedStyleSheets?.filter === 'function';
    } catch (err) {
      return false;
    }
  };

  const setFilterOnNative = () => {
    try {
      const sheets = doc.adoptedStyleSheets;
      if (sheets && typeof sheets.filter !== 'function') {
        const filterFn = Array.prototype.filter.bind(Array.from(sheets || []));
        try {
          Object.defineProperty(sheets, 'filter', { value: filterFn, configurable: true, writable: true });
        } catch (err) {
          sheets.filter = filterFn;
        }
      }
      return typeof doc.adoptedStyleSheets?.filter === 'function';
    } catch (err) {
      return false;
    }
  };

  if (setFilterOnNative()) return;
  if (applyDescriptor()) return;

  try {
    const fallback = normalize(buffer);
    doc.adoptedStyleSheets = fallback;
  } catch (err) {
    /* ignore */
  }

  const finalSheets = doc.adoptedStyleSheets || buffer;
  if (finalSheets && typeof finalSheets.filter !== 'function') {
    try {
      Object.defineProperty(Document.prototype, 'adoptedStyleSheets', {
        configurable: true,
        get() { return buffer; },
        set(value) {
          const next = normalize(value, buffer);
          buffer.splice(0, buffer.length, ...next);
        }
      });
    } catch (err) {
      // last resort: leave buffer attached even if native property is stubborn
      try {
        finalSheets.filter = Array.prototype.filter.bind(buffer);
      } catch (err2) {
        /* swallow */
      }
    }
  }
})(document);

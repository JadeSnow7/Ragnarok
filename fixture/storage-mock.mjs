/** Minimal Web Storage mock shared by the real Node regression tests. */
export class MemoryStorage {
  #items = new Map();
  writes = 0;

  constructor(entries = {}) {
    for (const [key, value] of Object.entries(entries)) {
      this.#items.set(String(key), String(value));
    }
  }

  getItem(key) {
    return this.#items.get(String(key)) ?? null;
  }

  setItem(key, value) {
    this.#items.set(String(key), String(value));
    this.writes += 1;
  }

  removeItem(key) {
    this.#items.delete(String(key));
  }

  clear() {
    this.#items.clear();
  }
}

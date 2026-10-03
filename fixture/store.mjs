export const STORAGE_KEY = 'handoff-todo-fixture:v1';

let fallbackSequence = 0;
const makeId = () => globalThis.crypto?.randomUUID?.()
  ?? `todo-${Date.now()}-${++fallbackSequence}`;

function readTodos(storage) {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (raw === null) return [];
    const saved = JSON.parse(raw);
    if (!Array.isArray(saved)) return [];
    const valid = saved.every(todo => todo && typeof todo === 'object'
      && typeof todo.id === 'string' && todo.id.length > 0
      && typeof todo.title === 'string' && todo.title.trim().length > 0
      && typeof todo.completed === 'boolean');
    if (!valid || new Set(saved.map(todo => todo.id)).size !== saved.length) return [];
    return saved.map(({ id, title, completed }) => ({ id, title, completed }));
  } catch {
    return [];
  }
}

/** A tiny browser-local store. A new instance models a page reload. */
export function createTodoStore(storage, { idFactory = makeId } = {}) {
  let todos = readTodos(storage);
  const persist = () => storage.setItem(STORAGE_KEY, JSON.stringify(todos));
  const list = () => todos.map(todo => ({ ...todo }));

  return {
    list,
    add(title) {
      if (typeof title !== 'string' || !title.trim()) return null;
      const todo = { id: idFactory(), title: title.trim(), completed: false };
      todos.push(todo);
      persist();
      return { ...todo };
    },
    toggle(id) {
      const todo = todos.find(item => item.id === id);
      if (!todo) return false;
      todo.completed = !todo.completed;
      // Known baseline bug: the in-memory toggle is not saved before reload.
      return true;
    },
    remove(id) {
      const remaining = todos.filter(todo => todo.id !== id);
      if (remaining.length === todos.length) return false;
      todos = remaining;
      persist();
      return true;
    },
  };
}

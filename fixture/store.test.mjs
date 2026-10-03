import test from 'node:test';
import assert from 'node:assert/strict';
import { createTodoStore, STORAGE_KEY } from './store.mjs';
import { MemoryStorage } from './storage-mock.mjs';

function setup() {
  let nextId = 0;
  const storage = new MemoryStorage();
  const store = createTodoStore(storage, { idFactory: () => `todo-${++nextId}` });
  return { store, storage };
}

test('starts empty when no saved todos exist', () => {
  const { store, storage } = setup();
  assert.deepEqual(store.list(), []);
  assert.equal(storage.writes, 0);
});

test('restores saved checked and unchecked todos', () => {
  const saved = [
    { id: 'one', title: 'Already checked', completed: true },
    { id: 'two', title: 'Still pending', completed: false },
  ];
  const storage = new MemoryStorage({ [STORAGE_KEY]: JSON.stringify(saved) });
  assert.deepEqual(createTodoStore(storage).list(), saved);
  assert.equal(storage.writes, 0);
});

test('adding a todo trims its title and persists it unchecked', () => {
  const { store, storage } = setup();
  const added = store.add('  Prepare the demo  ');
  assert.deepEqual(added, { id: 'todo-1', title: 'Prepare the demo', completed: false });
  assert.deepEqual(createTodoStore(storage).list(), [added]);
});

test('toggle changes only the selected todo in memory', () => {
  const { store } = setup();
  const selected = store.add('Selected');
  store.add('Unrelated');
  assert.equal(store.toggle(selected.id), true);
  assert.deepEqual(store.list().map(todo => todo.completed), [true, false]);
  assert.equal(store.toggle(selected.id), true);
  assert.deepEqual(store.list().map(todo => todo.completed), [false, false]);
});

test('checkbox state survives reload after toggling', () => {
  const { store, storage } = setup();
  const selected = store.add('Keep my checkbox checked');
  const unrelated = store.add('Leave this task unchecked');
  store.toggle(selected.id);
  assert.equal(store.list()[0].completed, true, 'the checkbox changes before reload');

  // New store + same storage reproduces a browser reload, not an in-memory check.
  const reloaded = createTodoStore(storage);
  assert.deepEqual(reloaded.list(), [
    { ...selected, completed: true },
    unrelated,
  ], 'checked state must survive a fresh store instance');

  reloaded.toggle(selected.id);
  assert.deepEqual(createTodoStore(storage).list(), [selected, unrelated],
    'unchecking must also survive another reload');
});

test('removing a todo persists and retains unrelated todos', () => {
  const { store, storage } = setup();
  const removed = store.add('Remove me');
  const retained = store.add('Keep me');
  assert.equal(store.remove(removed.id), true);
  assert.deepEqual(createTodoStore(storage).list(), [retained]);
});

test('blank titles and unknown ids do not mutate or write storage', () => {
  const { store, storage } = setup();
  const retained = store.add('Keep me');
  const writes = storage.writes;
  assert.equal(store.add('   '), null);
  assert.equal(store.add(null), null);
  assert.equal(store.toggle('missing'), false);
  assert.equal(store.remove('missing'), false);
  assert.deepEqual(store.list(), [retained]);
  assert.equal(storage.writes, writes);
});

test('callers cannot mutate state through returned objects', () => {
  const { store } = setup();
  const returned = store.add('Original');
  returned.title = 'Changed outside the store';
  const snapshot = store.list();
  snapshot[0].completed = true;
  snapshot.push({ id: 'rogue', title: 'Injected', completed: true });
  assert.deepEqual(store.list(), [{ id: 'todo-1', title: 'Original', completed: false }]);
});

test('corrupt storage is handled safely without rewriting it on read', () => {
  const invalidPayloads = [
    '{broken-json',
    'null',
    '{}',
    '[null]',
    '[{"id":"one","title":"Task","completed":"yes"}]',
    '[{"id":"one","title":"Task","completed":true},{"id":"one","title":"Duplicate","completed":false}]',
  ];
  for (const raw of invalidPayloads) {
    const storage = new MemoryStorage({ [STORAGE_KEY]: raw });
    assert.deepEqual(createTodoStore(storage).list(), [], `safe fallback for ${raw}`);
    assert.equal(storage.getItem(STORAGE_KEY), raw);
    assert.equal(storage.writes, 0);
  }
});

test('unavailable storage reads fall back to an empty list', () => {
  const storage = { getItem() { throw new Error('Storage access blocked'); } };
  assert.deepEqual(createTodoStore(storage).list(), []);
});

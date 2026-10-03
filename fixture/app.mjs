import { createTodoStore } from './store.mjs';

const form = document.querySelector('#add-form');
const input = document.querySelector('#new-todo');
const list = document.querySelector('#todos');
const empty = document.querySelector('#empty');
const count = document.querySelector('#count');
const status = document.querySelector('#status');
// Separate the baseline and every per-task preview, while retaining reload state.
const storagePrefix = `handoff-preview:${location.pathname}:`;
const scopedStorage = {
  getItem: key => localStorage.getItem(storagePrefix + key),
  setItem: (key, value) => localStorage.setItem(storagePrefix + key, value),
};
const store = createTodoStore(scopedStorage);

function render() {
  const todos = store.list();
  list.replaceChildren();
  for (const todo of todos) {
    const item = document.createElement('li');
    const label = document.createElement('label');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = todo.completed;
    const title = document.createElement('span');
    title.textContent = todo.title;
    label.append(checkbox, title);
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = 'Remove';
    remove.setAttribute('aria-label', `Remove ${todo.title}`);
    checkbox.addEventListener('change', () => {
      try {
        store.toggle(todo.id);
        const changed = store.list().find(item => item.id === todo.id);
        checkbox.checked = changed.completed;
        count.textContent = `${store.list().filter(item => item.completed).length} of ${store.list().length} completed`;
        status.textContent = 'Checkbox changed. Reload the fixture to check persistence.';
      } catch {
        status.textContent = 'Browser storage could not be updated.';
      }
    });
    remove.addEventListener('click', () => {
      try {
        store.remove(todo.id);
        render();
        status.textContent = 'Task removed.';
        input.focus();
      } catch {
        status.textContent = 'Browser storage could not be updated.';
      }
    });
    item.append(label, remove);
    list.append(item);
  }
  empty.hidden = todos.length > 0;
  count.textContent = `${todos.filter(todo => todo.completed).length} of ${todos.length} completed`;
}

form.addEventListener('submit', event => {
  event.preventDefault();
  try {
    if (!store.add(input.value)) return;
    input.value = '';
    render();
    status.textContent = 'Task added. Check its box and reload.';
    input.focus();
  } catch {
    status.textContent = 'Browser storage could not be updated.';
  }
});

document.querySelector('#reload').addEventListener('click', () => location.reload());
render();

import test from 'node:test';
import assert from 'node:assert/strict';
import { makeCard, readCard, MSGTYPE } from './card-contract.mjs';

test('exact message shape and readable fallback', () => {
  assert.deepEqual(makeCard('Web Studio Handoff', 'http://127.0.0.1:4173/'), {
    msgtype: MSGTYPE,
    body: '[Mini app] Web Studio Handoff\nhttp://127.0.0.1:4173/',
    mini_app: {version:1,title:'Web Studio Handoff',url:'http://127.0.0.1:4173/'},
  });
});
test('unicode title and encoded URL survive JSON roundtrip', () => {
  const card = makeCard('交付验收 Handoff', 'https://example.com/app?q=a%20b#result');
  assert.deepEqual(readCard(JSON.parse(JSON.stringify(card))), card.mini_app);
});
test('empty title falls back to hostname; surrounding spaces trimmed', () => {
  assert.equal(makeCard('  ', ' https://example.com/app ').mini_app.title, 'example.com');
});
test('HTTP loopback accepted for same-machine development only', () => {
  assert.equal(makeCard('Demo', 'http://127.0.0.1:8000/app').mini_app.url, 'http://127.0.0.1:8000/app');
});
test('120 Unicode code points accepted', () => assert.equal([...makeCard('测'.repeat(120),'https://example.com').mini_app.title].length,120));
test('121 Unicode code points rejected', () => assert.throws(() => makeCard('测'.repeat(121),'https://example.com')));
test('URL length uses UTF-8 bytes, not JS string length', () => assert.throws(() => makeCard('Demo','https://example.com/'+ '测'.repeat(1400))));
for (const address of [
  'javascript:alert(1)', 'file:///etc/passwd', 'data:text/html,test',
  'https://user:pass@example.com', 'https://user@example.com',
  'http://example.com/\nsecret', 'https://example.com/\u0000',
  'example.com', 'matrix:u/test:example.com', 'https://example.com/'+ 'a'.repeat(4096),
]) test(`reject unsafe/malformed URL: ${address.slice(0,70)}`, () => assert.throws(() => makeCard('Demo',address)));
test('title containing control character rejected', () => assert.throws(() => makeCard('test\nline','https://example.com')));
test('unknown version rejected on receipt', () => {
  const card=makeCard('Demo','https://example.com');card.mini_app.version=2;
  assert.throws(() => readCard(card));
});
test('malicious metadata rejected on receipt', () => {
  const card=makeCard('Demo','https://example.com');card.mini_app.url='javascript:alert(1)';
  assert.throws(() => readCard(card));
});
test('other message type rejected', () => assert.throws(() => readCard({msgtype:'m.text',body:'Hi'})));
test('missing or non-string fields rejected', () => {
  assert.throws(() => readCard({msgtype:MSGTYPE,mini_app:{version:1,title:7,url:'https://example.com'}}));
  assert.throws(() => readCard({msgtype:MSGTYPE}));
});

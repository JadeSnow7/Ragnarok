/**
 * Offline, source-informed check of the Rinx web mini-app message contract.
 * Source: hagency-org/Rinx c515e5fc9b6dc22e67f7d551b09fdd793ec685a1,
 * src/mini_app.rs (WebMiniApp::new/message/from_message).
 * This uses Node's URL parser. It is NOT the compiled Rust implementation
 * and does not establish native rendering or Matrix delivery.
 */
export const MSGTYPE = 'rs.robius.robrix.mini_app';
const control = /\p{Cc}/u;

export function makeCard(title, address) {
  if (typeof title !== 'string' || typeof address !== 'string') throw new Error('string fields required');
  address = address.trim();
  if (Buffer.byteLength(address, 'utf8') > 4096 || control.test(address)) throw new Error('invalid URL length/control');
  let url;
  try { url = new URL(address); } catch { throw new Error('complete URL required'); }
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname) throw new Error('HTTP(S) host required');
  if (url.username || url.password) throw new Error('embedded credentials forbidden');
  title = title.trim();
  if ([...title].length > 120 || control.test(title)) throw new Error('invalid title length/control');
  title ||= url.hostname;
  address = url.toString();
  return {
    msgtype: MSGTYPE,
    body: `[Mini app] ${title}\n${address}`,
    mini_app: { version: 1, title, url: address },
  };
}

export function readCard(message) {
  if (message?.msgtype !== MSGTYPE) throw new Error('wrong message type');
  if (message?.mini_app?.version !== 1) throw new Error('unsupported payload version');
  return makeCard(message.mini_app.title, message.mini_app.url).mini_app;
}

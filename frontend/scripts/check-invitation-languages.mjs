// Real Chromium layout checks with isolated API fixtures; no database writes.
// Run from frontend: node scripts/check-invitation-languages.mjs
import { spawn } from 'node:child_process';
import { mkdtemp, rm, mkdir, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import assert from 'node:assert/strict';

const origin = process.env.REPLIT_DEV_DOMAIN
  ? `https://${process.env.REPLIT_DEV_DOMAIN}` : 'http://127.0.0.1:5000';
const profile = await mkdtemp(`${tmpdir()}/invitation-browser-`);
const browser = spawn(process.env.CHROMIUM_BIN || 'chromium', [
  '--headless', '--no-sandbox', '--disable-dev-shm-usage',
  '--remote-debugging-port=9223', `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' });
let socket;
let sequence = 0;
const pending = new Map();
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const errors = [];
let providerType = 'DOCTOR';
let adminSession = false;
let saved = {};
const languages = [
  { id: 'en', name: 'English', code: 'en' },
  { id: 'fr', name: 'French', code: 'fr' },
  ...Array.from({ length: 24 }, (_, index) => ({
    id: `language-${index}`, name: `Language ${String(index).padStart(2, '0')}`, code: `l${index}`,
  })),
];
function fixture() {
  return {
    id: 'browser-invite', provider_type: providerType, recipient_email: 'fixture@example.com',
    emails_edited: true,
    provider: {
      name: 'Browser fixture', first_name: 'Avery', last_name: 'Quinn',
      description: null, email: null, phone: null, website: null,
      visit_stability: 'NOT_STABLE_VISIT', status: 'ACTIVE',
      specialization_ids: [], language_ids: ['en'], locations: [], phones: [],
      emails: [], photos: [], ...saved,
    },
  };
}
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const response = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  assert(!response.exceptionDetails, JSON.stringify(response.exceptionDetails));
  return response.result.value;
}
async function waitFor(expression) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (await evaluate(`!!(${expression})`)) return;
    await sleep(100);
  }
  console.error(await evaluate(`({url:location.href, text:document.body.innerText.slice(0,2000)})`), errors);
  throw new Error(`Timed out: ${expression}`);
}
async function click(selector) {
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center', behavior:'instant'})`);
  await sleep(100);
  const point = await evaluate(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)});
    const r = el.getBoundingClientRect();
    const x = r.x+r.width/2, y = r.y+r.height/2;
    const hit = document.elementFromPoint(x,y);
    return {x,y, hit:hit?.outerHTML.slice(0,300)};
  })()`);
  if (selector === '[role="option"]:last-child') console.log('Last option hit:', point);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', clickCount: 1, x:point.x, y:point.y });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', clickCount: 1, x:point.x, y:point.y });
  await sleep(100);
}
try {
  let target;
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      target = (await (await fetch('http://127.0.0.1:9223/json/list')).json()).find((item) => item.type === 'page');
      if (target) break;
    } catch {}
    await sleep(100);
  }
  assert(target, 'Chromium did not start');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve) => socket.addEventListener('open', resolve, { once: true }));
  socket.addEventListener('message', async (event) => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const callback = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) callback.reject(new Error(JSON.stringify(message.error)));
      else callback.resolve(message.result);
    } else if (message.method === 'Runtime.exceptionThrown') {
      errors.push(message.params.exceptionDetails.text);
    } else if (message.method === 'Fetch.requestPaused') {
      const { requestId, request } = message.params;
      const path = new URL(request.url).pathname;
      let body = {};
      let status = 200;
      if (path.endsWith('/auth/refresh')) {
        if (adminSession) body = { access_token: 'browser-fixture', user: {
          id: 'fixture-admin', email: 'fixture@example.com', full_name: 'Fixture admin',
          roles: ['admin'], role: 'admin', is_active: true,
        } };
        else { status = 401; body = { detail: 'No fixture session' }; }
      }
      else if (path.endsWith('/auth/provider-languages')) body = languages;
      else if (path.endsWith('/languages')) body = { data: languages, meta: { total_pages: 1 } };
      else if (path.endsWith('/auth/provider-specializations')) body = [];
      else if (path.endsWith('/specializations')) body = { data: [], meta: { total_pages: 1 } };
      else if (path.endsWith('/save')) {
        saved = JSON.parse(request.postData);
        body = fixture();
      } else if (path.includes('/provider/invitations/')) body = fixture();
      await send('Fetch.fulfillRequest', {
        requestId, responseCode: status,
        responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
        body: Buffer.from(JSON.stringify(body)).toString('base64'),
      });
    }
  });
  await send('Runtime.enable');
  await send('Page.enable');
  await send('Fetch.enable', { patterns: [{ urlPattern: `${origin}/api/*` }] });
  const trigger = '[aria-labelledby="languages-label"]';
  for (const mobile of [false, true]) {
    await send('Emulation.setDeviceMetricsOverride', {
      width: mobile ? 390 : 1280, height: mobile ? 844 : 900,
      deviceScaleFactor: 1, mobile,
    });
    await send('Emulation.setTouchEmulationEnabled', { enabled: mobile });
    for (providerType of ['DOCTOR', 'CLINIC', 'HOSPITAL']) {
      saved = {};
      await send('Page.navigate', { url: `${origin}/provider/invite/browser-fixture` });
      await waitFor(`document.querySelector('${trigger}')?.disabled === false`);
      await click(trigger);
      await waitFor(`document.querySelector('[aria-label="Search languages"]')`);
      const layout = await evaluate(`(() => {
        const menu = document.querySelector('#languages-list');
        const card = menu.closest('[class*="card--pad-lg"]');
        const r = menu.getBoundingClientRect(), c = card.getBoundingClientRect();
        return {overflow: getComputedStyle(card).overflow, zIndex: getComputedStyle(card).zIndex,
          menuBottom:r.bottom, cardBottom:c.bottom, left:r.left, right:r.right,
          width:innerWidth, pageWidth:document.documentElement.scrollWidth};
      })()`);
      console.log(providerType, mobile ? 'mobile' : 'desktop', layout);
      assert.equal(layout.overflow, 'visible');
      assert.equal(layout.zIndex, providerType === 'DOCTOR' ? '5' : '6');
      assert(layout.left >= 0 && layout.right <= layout.width);
      assert(layout.pageWidth <= layout.width, 'Horizontal overflow');
      // Scroll the options at the footer boundary, then use a real pointer hit.
      assert(await evaluate(`(() => {
        const list = document.querySelector('[role="listbox"][aria-label="Languages"]');
        return getComputedStyle(list).overflowY === 'auto' && list.scrollHeight > list.clientHeight;
      })()`), 'Options must have a scrollable viewport');
      await evaluate(`document.querySelector('[role="listbox"][aria-label="Languages"]').scrollTop = 1000`);
      await click('[role="option"]:last-child');
      assert(await evaluate(`!!document.querySelector('[aria-label="Remove Language 23"]')`));
      await evaluate(`document.querySelector('[aria-label="Search languages"]').focus()`);
      await send('Input.insertText', { text: 'French' });
      await waitFor(`document.querySelectorAll('#languages-list [role="option"]').length === 1`);
      await click('#languages-list [role="option"]');
      assert(await evaluate(`!!document.querySelector('[aria-label="Remove French"]')`));
      await click('[aria-label="Remove English"]');
      await click('h1');
      assert(await evaluate(`!document.querySelector('#languages-list')`));
      await evaluate(`Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Save draft').click()`);
      await waitFor(`document.querySelector('[role="status"]')`);
      assert.deepEqual(saved.language_ids, ['language-23', 'fr']);
      await send('Page.reload');
      await sleep(500);
      await waitFor(`document.querySelector('[aria-label="Remove French"]')`);
      await click(trigger);
      assert(await evaluate(`document.querySelector('[role="option"][aria-selected="true"]').textContent.includes('French')`));
      await mkdir('../.cache/invitation-languages', { recursive: true });
      const screenshot = await send('Page.captureScreenshot');
      await writeFile(`../.cache/invitation-languages/${providerType}-${mobile ? 'mobile' : 'desktop'}.png`,
        Buffer.from(screenshot.data, 'base64'));
    }
    // Smoke-check both shared-picker consumers with unchanged dark/light styles.
    for (const path of ['/provider/signup', '/admin/providers/new']) {
      adminSession = path.startsWith('/admin/');
      await send('Page.navigate', { url: `${origin}${path}` });
      await waitFor(`document.querySelector('${trigger}')?.disabled === false`);
      await click(trigger);
      await waitFor(`document.querySelector('[aria-label="Search languages"]')`);
      await send('Input.insertText', { text: 'French' });
      await waitFor(`document.querySelectorAll('#languages-list [role="option"]').length === 1`);
      await click('#languages-list [role="option"]');
      assert(await evaluate(`!!document.querySelector('[aria-label="Remove French"]')`));
      await click('[aria-label="Search languages"]');
      await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape' });
      await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape' });
      assert(await evaluate(`!document.querySelector('#languages-list')`));
      console.log(path, mobile ? 'mobile' : 'desktop', 'smoke check passed');
    }
    adminSession = false;
  }
  assert.deepEqual(errors, []);
  console.log('Invitation language browser checks passed');
} finally {
  socket?.close();
  browser.kill();
  await sleep(300);
  await rm(profile, { recursive: true, force: true });
}
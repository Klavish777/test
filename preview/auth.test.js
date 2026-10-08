import test from 'node:test';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

/*
 * Тесты авторизации в прототипе. Инварианты здесь те же, что в
 * android/app/src/test/java/work/day/app/AuthTest.kt: вход не обязателен,
 * scope только на чтение, пароль нигде не сохраняется, state в OAuth обязателен.
 */
const stub = () => ({
  textContent: '', innerHTML: '', value: '', classList: { add() {}, remove() {} }, style: {},
});
const cache = new Map();
globalThis.document = { getElementById: (id) => (cache.has(id) ? cache.get(id) : cache.set(id, stub()).get(id)) };
globalThis.window = globalThis;

const src = readFileSync(new URL('./app.js', import.meta.url), 'utf8');
let E = null;
globalThis.__WORKDAY_TEST_HOOK__ = (api) => { E = api; };
new Function(src)();
assert.ok(E, 'app.js не отдал API тесту');

const { S, A } = E;
const fresh = () => {
  S.auth = {
    session: { links: [], email: '', guest: false, lockEnabled: false, passwordHash: '', passwordSalt: '' },
    clients: { google: '', tiktok: '', firebase: '', redirect: 'workdayauth://oauth2callback' },
    backend: 'local',
  };
};

test('вход не обязателен: без сессии показываем экран входа, «без входа» снимает гейт', () => {
  fresh();
  assert.equal(A.needsAuth(), true);
  S.auth.session.guest = true;
  assert.equal(A.needsAuth(), false);
});

test('ссылка на провайдер без client id невозможна, а не «битон»', () => {
  fresh();
  for (const p of ['google', 'tiktok']) assert.match(A.beginLink(p).error, /настройках/);
  // отказ не должен оставлять «висящую» попытку: иначе поздний редирект был бы принят
  assert.equal(A.completeLink('любой-state', { code: 'c' }).ok, false);
});

test('запрашиваются только scope на чтение — publish/upload запрещены', () => {
  fresh();
  S.auth.clients.google = 'cid.apps.googleusercontent.com';
  S.auth.clients.tiktok = 'awclientkey';
  const banned = ['upload', 'force-ssl', 'insert', 'update', 'delete', 'moderation', 'publish'];
  for (const p of ['google', 'tiktok']) {
    for (const scope of A.scopesFor(p)) {
      assert.ok(!banned.some((b) => scope.includes(b)), `${p}: запрещённый scope ${scope}`);
    }
    const r = A.beginLink(p);
    assert.ok(r.ok);
    assert.match(r.url, /response_type=code/);
    assert.ok(r.url.includes('code_challenge_method=S256'), 'Google обязан идти по PKCE без секрета');
    assert.ok(r.url.includes(encodeURIComponent(S.auth.clients.redirect)), 'redirect должен совпадать с манифестом');
    const sent = new URL(r.url).searchParams.get('scope');
    if (p === 'tiktok') assert.ok(sent.includes(','), 'TikTok ждёт scope через запятую');
    else assert.ok(!sent.includes(','), 'Google ждёт scope через пробел');
  }
});

test('редирект без state или с ошибкой не создаёт доступ', () => {
  fresh();
  S.auth.clients.google = 'cid';
  const start = A.beginLink('google');
  assert.ok(start.ok);
  assert.equal(A.completeLink('не-тот-state', { code: 'c' }).ok, false);

  A.beginLink('google');
  assert.match(A.completeLink(null, { error: 'access_denied' }).error, /отказ/);

  const again = A.beginLink('google');
  assert.equal(A.completeLink(new URL(again.url).searchParams.get('state'), { code: 'c' }).ok, true);
  assert.equal(S.auth.session.links.length, 1);
  assert.equal(A.completeLink('state-после-завершения', { code: 'c' }).ok, false, 'pending обязан быть одноразовым');
});

test('подключённый канал отдаёт id в профиль — цифры приходят от Google, а не от нас', () => {
  fresh();
  S.auth.clients.google = 'cid';
  const { url } = A.beginLink('google');
  const st = new URL(url).searchParams.get('state');
  const r = A.completeLink(st, { code: 'c', followers: 12345, name: 'Мой канал' });
  assert.equal(r.ok, true);
  assert.equal(S.profile.youtube, r.link.subject);
  assert.equal(S.auth.session.links[0].followers, 12345);
  assert.ok(A.expiryText(S.auth.session.links[0]).includes('мин'));
  A.revoke('google');
  assert.equal(S.auth.session.links.length, 0);
});

test('локальный аккаунт: пароль не сохраняется даже в памяти состояния', () => {
  fresh();
  assert.ok(A.checkCredentials('иван', '123456', '123456', 'register').length >= 1, 'email без @ не проходит');
  assert.ok(A.register('иван', 'short', 'short').errors.length > 0, 'короткий пароль не проходит');

  const r = A.register('AUTHOR@Example.com', 'secret-pass', 'secret-pass');
  assert.ok(r.ok, JSON.stringify(r.errors));
  const stored = JSON.stringify(S);
  assert.ok(!stored.includes('secret-pass'), 'пароль попал в сериализуемое состояние');
  assert.equal(S.auth.session.email, 'author@example.com', 'email нормализуется');
  assert.ok(S.auth.session.passwordHash.length >= 32 && !S.auth.session.passwordHash.includes('secret-pass'));
  assert.equal(S.auth.session.lockEnabled, true, 'пароль на устройстве обязан поставить замок');

  assert.equal(A.signIn('author@example.com', 'wrong-pass').ok, false);
  assert.equal(A.signIn('other@example.com', 'secret-pass').ok, false);
  assert.equal(A.signIn('author@example.com', 'secret-pass').ok, true);
});

test('замок проверяется локально и снимается только верным паролем', () => {
  fresh();
  S.auth.clients.google = 'cid';
  A.register('author@example.com', 'secret-pass', 'secret-pass');
  assert.equal(A.isLocked(), true, 'регистрация обязана включить замок');
  assert.equal(A.unlock('не-тот'), false);
  assert.equal(A.isLocked(), true);
  assert.equal(A.unlock('secret-pass'), true);
  assert.equal(A.isLocked(), false);
});

test('экран входа и разблокировки рисуются без undefined и не выдают токены', () => {
  fresh();
  const auth = E.viewAuth();
  assert.ok(!auth.includes('undefined'), 'в разметке экрана входа есть undefined');
  assert.ok(auth.includes('TikTok') && auth.includes('Без входа'));
  assert.ok(!/ya29\.|access_token|refresh_token/.test(auth), 'в разметке светится токен');

  A.register('author@example.com', 'secret-pass', 'secret-pass');
  const lock = E.viewLock();
  assert.ok(!lock.includes('undefined') && lock.includes('Пароль'));

  A.forceUnlock();
  const account = E.viewAccount();
  assert.ok(!account.includes('undefined'));
  assert.ok(account.includes('Ни один провайдер не привязан'));
  assert.ok(account.includes('локальный режим') || account.includes('локальный хеш'));
});

test('режимы логина: без Firebase — локальный хеш, с Firebase — считаем себя в Cloud', () => {
  fresh();
  A.register('author@example.com', 'secret-pass', 'secret-pass');
  assert.equal(S.auth.backend, 'local');
  fresh();
  S.auth.clients.firebase = 'AIza-demo';
  A.register('author@example.com', 'secret-pass', 'secret-pass');
  assert.equal(S.auth.backend, 'firebase');
});

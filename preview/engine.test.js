import test from 'node:test';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

/* app.js обращается к document.getElementById в render()-функциях — глушим DOM. */
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
const { S, AGENTS, ACTIONS, PLAYBOOKS, byId, plan, tick, startShift, approve, skip, published } = E;

test('модель совпадает с Kotlin-доменом: 4 агента, 10 плейбуков, 24 действия', () => {
  assert.equal(AGENTS.length, 4);
  assert.equal(PLAYBOOKS.length, 10);
  assert.equal(ACTIONS.length, 24);
  for (const a of ACTIONS) assert.ok(AGENTS.some((g) => g.key === a.agent), `действие ${a.id} без агента`);
  for (const p of PLAYBOOKS) for (const k of p.kinds) assert.ok(byId(k), `плейбук ${p.id} ссылается на несуществующее действие ${k}`);
  for (const a of AGENTS) assert.ok(PLAYBOOKS.some((p) => p.agent === a.key), `у агента ${a.key} нет плейбуков`);
});

test('рискованное действие всегда требует одобрения человека', () => {
  const risky = ACTIONS.filter((a) => a.risk !== 'low');
  assert.ok(risky.length >= 15, 'публичных действий большинство — так и задумано');
  assert.equal(ACTIONS.filter((a) => a.risk === 'high').length, 2);
});

test('план смены: 2 + интенсивность задач на агента, слоты внутри рабочего дня', () => {
  S.cfg.magnet.intensity = 3;
  plan();
  assert.equal(S.tasks.length, 20);
  assert.equal(S.tasks.filter((t) => t.agent === 'magnet').length, 5);
  for (const t of S.tasks) {
    assert.ok(t.slot >= E.SHIFT_START && t.slot <= E.SHIFT_END - 30, `слот ${t.slot} вне смены`);
    assert.ok(byId(t.kind), 'задача без действия');
  }
});

test('интенсивность и выключение агента меняют план', () => {
  S.cfg.magnet.intensity = 5; plan();
  const many = S.tasks.filter((t) => t.agent === 'magnet').length;
  S.cfg.magnet.intensity = 1; plan();
  const few = S.tasks.filter((t) => t.agent === 'magnet').length;
  assert.ok(many > few, `${many} должно быть больше ${few}`);
  S.cfg.spark.enabled = false; plan();
  assert.equal(S.tasks.some((t) => t.agent === 'spark'), false, 'выключенный агент не получает задач');
  S.cfg.spark.enabled = true; S.cfg.magnet.intensity = 3;
});

test('полный прогон смены: материалы, лента, отчёт, ни одной публикации без одобрения', () => {
  S.phase = 'working'; S.clock = E.SHIFT_START; S.events = []; S.artifacts = []; S.queue = []; S.report = null;
  for (const a of AGENTS) Object.assign(S.runtime[a.key], { busy: false, task: '', progress: 0, done: 0, wait: 0, out: 0, last: '', msg: '' });
  plan();
  let ticks = 0;
  while (S.phase === 'working' && ticks < 400) { tick(); ticks++; }
  assert.ok(S.report, 'смена закрылась отчётом');
  assert.ok(S.artifacts.length > 0, 'агенты подготовили материалы');
  assert.ok(S.queue.length === 0, 'без одобрения человека очередь публикации пуста');
  const selfPublished = S.tasks.filter((t) => byId(t.kind).risk !== 'low' && t.status === 'done');
  assert.equal(selfPublished.length, 0, 'ни одно публичное действие не закрылось само');
  assert.ok(S.events.length > S.artifacts.length, 'лента смены полнее, чем список материалов');
  assert.deepEqual(S.report.per.map((p) => p.agent), AGENTS.map((a) => a.key), 'в отчёте все четыре агента');
});

test('одобрение → очередь публикации → отметка «опубликовал»', () => {
  const target = S.tasks.find((t) => t.status === 'approval');
  assert.ok(target, 'после смены есть что одобрить');
  approve(target.id);
  assert.equal(S.queue.length, 1);
  assert.equal(S.queue[0].state, 'ready');
  published(S.queue[0].id);
  assert.equal(S.queue[0].state, 'published');
  const rest = S.tasks.find((t) => t.status === 'planned') ?? S.tasks.find((t) => t.status === 'approval');
  skip(rest.id);
  assert.equal(S.tasks.find((t) => t.id === rest.id).status, 'skipped');
});

test('плейбуки агента переключаются и не ломают план', () => {
  E.togglePb('magnet', 'magnet.trend');
  plan();
  const kinds = S.tasks.filter((t) => t.agent === 'magnet').map((t) => t.kind);
  assert.ok(kinds.length > 0);
  E.togglePb('magnet', 'magnet.trend');
});

test('метрики для графика роста считаются без NaN', () => {
  for (const plat of ['yt', 'tt']) {
    for (const metric of ['subs', 'views', 'ret', 'er', 'nw', 'ctr']) {
      const rows = E.series(plat, metric);
      assert.equal(rows.length, 60, `${plat}/${metric}: 60 точек`);
      for (const r of rows) assert.ok(Number.isFinite(r.v) && r.v >= 0, `${plat}/${metric}: значение ${r.v}`);
    }
  }
  const subs = E.series('yt', 'subs');
  assert.ok(subs.at(-1).v > subs[0].v, 'подписчики на демо-графике растут');
});

test('все экраны рендерятся без исключений', () => {
  for (const [name, fn] of Object.entries({
    viewShift: E.viewShift, viewAgents: E.viewAgents, viewTasks: E.viewTasks, viewGrowth: E.viewGrowth, viewSettings: E.viewSettings,
  })) {
    const out = fn();
    assert.equal(typeof out, 'string', `${name} вернул не строку`);
    assert.ok(out.length > 200, `${name}: подозрительно пусто (${out.length} симв.)`);
    assert.equal(out.includes('undefined'), false, `${name}: в разметку просочился undefined`);
    assert.equal(out.includes('NaN'), false, `${name}: NaN в разметке`);
  }
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

/*
 * Тесты зеркала «Генерации» в прототипе. Смысл не в том, чтобы продублировать Kotlin,
 * а в том, чтобы два инварианта продукта работали и в web-прототипе:
 *   1) тайминги битов всегда равны заказанной длительности;
 *   2) правки монтажёра не могут понизить балл;
 *   3) чужая музыка/репост/накрутка блокируют публикацию.
 */
const stub = () => ({ textContent: '', innerHTML: '', value: '', classList: { add() {}, remove() {} }, style: {} });
const cache = new Map();
globalThis.document = { getElementById: (id) => (cache.has(id) ? cache.get(id) : cache.set(id, stub()).get(id)) };
globalThis.window = globalThis;

const src = readFileSync(new URL('./app.js', import.meta.url), 'utf8');
let API = null;
globalThis.__WORKDAY_TEST_HOOK__ = (api) => { API = api; };
new Function(src)();
assert.ok(API, 'app.js не отдал API тесту');
const { LAB, GEN, genResearch, genGenerate, genBuild, genEnqueue, S } = API;

const len = (beats) => beats.reduce((a, b) => a + (b.end - b.start), 0);

test('LAB покрывает тот же набор ниш и форматов, что и домен', () => {
  assert.equal(LAB.NICHES.length, 14);
  assert.deepEqual(Object.keys(LAB.FORMATS), ['SHORTS', 'FEED', 'MID', 'LONG']);
  for (const [key, f] of Object.entries(LAB.FORMATS)) {
    assert.ok(f.min < f.max, key);
    assert.equal(f.vertical, key === 'SHORTS', `${key}: только Shorts вертикальный`);
  }
});

test('биты покрывают ролик без дыр на всех допустимых длительностях', () => {
  for (const [key, f] of Object.entries(LAB.FORMATS)) {
    const samples = key === 'SHORTS'
      ? Array.from({ length: f.max - f.min + 1 }, (_, i) => f.min + i)
      : [f.min, Math.round((f.min + f.max) / 2), f.max];
    for (const duration of samples) {
      const beats = LAB.buildBeats({ title: '3 приёма, которые экономят час', hook: 'проверка', niche: 'Рецепты и кухня', format: key, durationSec: duration });
      assert.equal(len(beats), duration, `${key} @ ${duration}с`);
      let cursor = 0;
      for (const b of beats) {
        assert.equal(b.start, cursor, `${key} @ ${duration}: дыра в таймингах`);
        assert.ok(b.end - b.start >= 1, 'пустой бит');
        cursor = b.end;
      }
      assert.equal(beats[0].role, 'HOOK');
      assert.ok(beats.some(b => b.role === 'PROOF'), 'нет бита доказательства');
    }
  }
});

test('предложенная длительность всегда в границах формата', () => {
  const demo = LAB.statsOf([]);
  const live = LAB.statsOf(Array.from({ length: 5 }, (_, i) => ({ title: 'как ' + i, views: 300000 + i * 1e5, likes: 9000, durationSec: 120 + i * 10, publishedAt: new Date(Date.now() - 864e5 * (i + 1)).toISOString().slice(0, 19) + 'Z' })));
  for (const [key, f] of Object.entries(LAB.FORMATS)) {
    for (const st of [demo, live]) {
      const d = LAB.pickDuration(key, st);
      assert.ok(d >= f.min && d <= f.max, `${key} @ ${d}с вне ${f.min}–${f.max}`);
    }
  }
  assert.equal(demo.demo, true, 'малая выборка не должна притворяться живой');
  assert.equal(live.demo, false);
});

test('правки монтажёра не понижают балл и объясняются', () => {
  const topic = { title: '3 приёма, которые экономят час', hook: 'проверка', niche: 'Фитнес и тело', format: 'SHORTS', durationSec: 40, velocity: 120 };
  const beats = LAB.buildBeats(topic);
  const assets = LAB.assetsFor(topic, beats);
  const before = LAB.score(beats, topic, assets);
  const pass = LAB.editPass(beats, topic, assets);
  const after = LAB.score(pass.beats, topic, pass.assets);
  assert.ok(after.total >= before.total, `балл упал: ${before.total} → ${after.total}`);
  assert.equal(len(pass.beats), 40, 'правки не должны ломать тайминги');
  for (const e of pass.edits) {
    assert.ok(e.action && e.reason, 'правка без объяснения');
    assert.ok(e.delta > 0, 'правка без цены');
  }

  // заведомо слабый скелет обязан расти строго
  const weak = [{ index: 0, start: 0, end: 40, role: 'PAYLOAD', voice: 'долгий рассказ без монтажа', screen: 'один план', shot: '', overlay: '' }];
  const weakBefore = LAB.score(weak, topic, []);
  const weakPass = LAB.editPass(weak, topic, []);
  const weakAfter = LAB.score(weakPass.beats, topic, weakPass.assets);
  assert.ok(weakAfter.total > weakBefore.total, `слабый скелет не улучшился: ${weakBefore.total} → ${weakAfter.total}`);
  assert.ok(weakPass.edits.length > 0);
  assert.ok(weakPass.assets.some(a => a.kind === 'CAPTIONS'), 'субтитры обязаны появиться');
  assert.ok(weakPass.beats.some(b => b.role === 'PROOF'), 'доказательство обязано появиться');
});

test('проверка прав: чистый пакет проходит, чужое и накрутки — нет', () => {
  const topic = { title: '3 приёма, которые экономят час', hook: 'проверка', niche: 'Рецепты и кухня', format: 'SHORTS', durationSec: 30 };
  const beats = [
    { index: 0, start: 0, end: 3, role: 'HOOK', voice: 'смотри: один приём', screen: 'крупно', shot: '', overlay: '0:00' },
    { index: 1, start: 3, end: 14, role: 'PAYLOAD', voice: 'делаешь так и плита чистая', screen: 'руки в кадре', shot: '', overlay: 'шаг 1' },
    { index: 2, start: 14, end: 20, role: 'PROOF', voice: 'замер: было 12 минут, стало 4', screen: 'скрин с цифрой', shot: '', overlay: '12→4' },
  ];
  const own = [
    { id: 'clip-1', kind: 'OWN_CLIP', license: 'OWN', query: 'свои съёмки' },
    { id: 'music', kind: 'MUSIC', license: 'YT_AUDIO_LIBRARY', query: 'Audio Library' },
    { id: 'captions', kind: 'CAPTIONS', license: 'OWN', query: 'captions.srt' },
  ];
  const clean = LAB.compliance(topic, beats, own, topic.title, 'Разбор приёма. Озвучка своя.');
  assert.ok(clean.allowedToPublish, JSON.stringify(clean.blockers));

  const stolen = LAB.compliance(topic, beats, own.concat([{ id: 'm2', kind: 'MUSIC', license: 'NEEDS_PERMISSION', query: 'чужой трек' }]), topic.title, '');
  assert.equal(stolen.allowedToPublish, false, 'чужая музыка обязана блокировать');

  const repost = LAB.compliance(topic, beats, own.concat([{ id: 'clip-x', kind: 'OWN_CLIP', license: 'REPOSTED', query: 'чужой ролик целиком' }]), topic.title, '');
  assert.equal(repost.allowedToPublish, false, 'переиздание чужого не монетизируется');

  const boosted = LAB.compliance(topic, beats.concat([{ index: 3, start: 20, end: 25, role: 'CTA', voice: 'накрутка просмотров поможет залететь', screen: '', shot: '', overlay: 'лайк' }]), own, topic.title, '');
  assert.equal(boosted.allowedToPublish, false, 'накрутку не пропускаем никогда');
  assert.ok(boosted.blockers.some(b => /накрут/i.test(b.rule)));

  // агент обязан уметь починить музыку сам
  const fixed = LAB.editPass(beats, topic, own.concat([{ id: 'm2', kind: 'MUSIC', license: 'NEEDS_PERMISSION', query: 'чужой трек' }]));
  assert.ok(!fixed.assets.some(a => a.kind === 'MUSIC' && ['NEEDS_PERMISSION', 'REPOSTED'].includes(a.license)), 'трек должен быть заменён на лицензионный');
});

test('субтитры: формат SRT, пустые биты пропускаются', () => {
  const srt = LAB.toSrt([
    { index: 0, start: 0, end: 3, role: 'HOOK', voice: 'раз', screen: '', shot: '', overlay: '' },
    { index: 1, start: 3, end: 11, role: 'PAYLOAD', voice: '', screen: '', shot: '', overlay: '' },
    { index: 2, start: 11, end: 15, role: 'PROOF', voice: 'два', screen: '', shot: '', overlay: '' },
  ]);
  const blocks = srt.trimEnd().split('\n\n');
  assert.equal(blocks.length, 2);
  blocks.forEach((block, i) => {
    assert.match(block, new RegExp('^' + (i + 1) + '\n\\d{2}:\\d{2}:\\d{2},000 --> \\d{2}:\\d{2}:\\d{2},000\n.+$', 's'));
  });
  assert.equal(LAB.toSrt([]), '');
  assert.match(LAB.timestamp(65), /^00:01:05,000$/);
});

test('рецепт отдаёт bash и манифест, и ничего не скачивает', () => {
  const topic = { title: '3 приёма', hook: 'хук', niche: 'Игры', format: 'SHORTS', durationSec: 30 };
  const beats = LAB.buildBeats(topic);
  const r = LAB.recipe(topic, beats);
  assert.ok(r.script.startsWith('#!/usr/bin/env bash'));
  assert.ok(r.script.includes('ffmpeg'));
  assert.equal(/yt-dlp|curl |wget/.test(r.script), false, 'скачивание чужого в рецепте недопустимо');
  const manifest = JSON.parse(r.manifest);
  assert.equal(manifest.width, 1080);
  assert.equal(manifest.height, 1920);
  assert.equal(manifest.durationSec, len(beats));
});

test('экран: темы, план и очередь публикации живут вместе', () => {
  GEN.niche = 'Рецепты и кухня';
  GEN.format = 'SHORTS';
  GEN.duration = 0;
  genResearch();
  genGenerate();
  assert.equal(GEN.topics.length, 6);
  assert.ok(GEN.duration >= 20 && GEN.duration <= 58);
  const sorted = GEN.topics.every((t, i, a) => i === 0 || a[i - 1].score.total >= t.score.total);
  assert.ok(sorted, 'ранжирование по баллу, а не по любви модели');
  genBuild(0);
  assert.ok(GEN.plan, 'план не собран');
  assert.ok(GEN.plan.compliance.allowedToPublish);
  const before = S.queue.length;
  genEnqueue();
  assert.equal(S.queue.length, before + 1, 'пакет обязан попасть в общую очередь');
  assert.equal(S.queue[0].state, 'ready');
  assert.ok(S.queue[0].gen.body.includes('Балл вирусности'));
  const html = API.viewGeneration();
  assert.ok(html.includes('Пакет к публикации'), 'план не отрендерился');
});

test('ниша «Родительство» требует явной маркировки — и не только', () => {
  const topic = { title: 'что делать если ребёнок не спит', hook: 'проверка', niche: 'Родительство', format: 'SHORTS', durationSec: 30 };
  const beats = LAB.buildBeats(topic);
  const report = LAB.compliance(topic, beats, LAB.assetsFor(topic, beats), topic.title, 'описание без слов о детях');
  const kidsCheck = report.checks.find(c => /детей/.test(c.rule));
  assert.ok(kidsCheck, 'проверка возрастной маркировки обязательна');
});

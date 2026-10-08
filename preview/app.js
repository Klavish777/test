/* ═══════════════════════════════════════════════════════════════════
   Данные точно те же, что в Kotlin-модели: 4 агента, 8 плейбуков, 24 действия.
   ═══════════════════════════════════════════════════════════════════ */
const AGENTS = [
  {key:'magnet', emoji:'🧲', name:'Магнит', dir:'Прирост аудитории', accent:'#5b5cff',
   mission:'Превращать показы в подписчиков: находимость, упаковка, воронка подписки.',
   kpi:'чистый прирост подписчиков / нед · CTR обложек · подписчики на 1000 просмотров'},
  {key:'scout', emoji:'🛰️', name:'Разведчик', dir:'Привлечение аудитории', accent:'#12b886',
   mission:'Приводить новых зрителей извне: нарезки, коллаборации, посевы, локализация.',
   kpi:'охват · доля новой аудитории · переходы Shorts → длинное'},
  {key:'booster', emoji:'⚡', name:'Ускоритель', dir:'Ускорение роста', accent:'#ff8a3d',
   mission:'Находить то, что уже работает, и масштабировать это: эксперименты, ритм, репаковка.',
   kpi:'скорость роста (нед/нед) · удержание · стабильность публикаций'},
  {key:'spark', emoji:'✨', name:'Искра', dir:'Стимулирование активности', accent:'#ffd23f',
   mission:'Раскачивать комьюнити, чтобы отклик был в первый час после публикации.',
   kpi:'ER · комментариев на ролик · ответы ≤ 1 часа · сохранения'},
];

const K = (id,agent,title,what,out,risk,effort,impact,metric,output)=>({id,agent,title,what,out,risk,effort,impact,metric,output});
const ACTIONS = [
  // Магнит
  K('seo_rewrite','magnet','Переупаковка заголовков под поиск','ищет запросы нишы и переписывает заголовки под них','5 вариантов заголовка + описание','low',25,.85,'конверсия показ → подписка',
    ['1. «Съёмка на телефон: 5 кадров, которые вытянут ролик» — ключ в первых 30 символах, обещание конкретной выгоды.','2. «Свет из окна против кольца: замер на одном сюжете» — сравнение всегда кликабельно.','3. «Почему твои Shorts не смотрят дальше 3-й секунды» — боль аудитории названа прямо.','Почему сработает: каждый заголовок обещает проверяемый результат, а не «секрет успеха».']),
  K('thumbnail_ab','magnet','A/B тест обложек','формулирует 2 концепции обложки и гипотезу по CTR','ТЗ для обложек + план теста','medium',20,.8,'CTR обложек',
    ['Обложка A: крупный план, 3 слова «СВЕТА НЕТ», фон тёмный, объект справа.','Обложка B: до/после слева направо, цифра в кадре «+38%», лицо с эмоцией.','Победа: CTR выше медианы канала на 15% при выборке от 3000 показов.','Тест: 48 часов на каждую, дальше оставляем одну для всего плейлиста.']),
  K('funnel_audit','magnet','Аудит воронки подписки','смотрит, на каких роликах зритель уходит не подписавшись','отчёт по воронке + 3 правки','low',35,.9,'подписчики на 1000 просмотров',
    ['Показ → клик: узкое место — обложка не читается в мобильной ленте (мелкий текст).','Клик → 3 сек: первые кадры не повторяют обещание заголовка → доскакивают и уходят.','3 сек → середина: провал на смене темы, нужен рестарт внимания.','Правки в 3 следующих роликах: хук-двойник, обещание продолжения, закреплённый комментарий.']),
  K('trend_jack','magnet','Вход в тренд за 24–48 часов','отбирает тренды, которые подходят нише','тренд + хук + сценарий 45 сек','medium',30,.75,'доля просмотров из тренда',
    ['Формат: 45 секунд, одна мысль, съёмка с телефона без монтажа света.','Хук 0–1.5 с: «Если ты снимаешь на телефон — у тебя лишний кадр».','Сценарий: завязка 5 с → 3 блока пользы по 8 с → вывод 6 с → вопрос залу 3 с.','Правило: окно старше 48 часов не снимаем, ждём следующее.']),
  K('series_plan','magnet','Серия «продолжение»','проектирует 5 эпизодов, где подписка = не потерять продолжение','сетка серий + клиффхэнгеры','medium',40,.85,'повторные просмотры',
    ['Эп1 «Первый кадр» → финал: «завтра разберу, почему он дрожит».','Эп2 «Свет» → финал: «этот приём убивает картинку, покажу завтра».','Эп3 «Звук» → финал: «без этого микрофона слушать невозможно».','Плейлист «Съёмка на телефон · сезон 1», в 1-м эпизоде закреплены ссылки на остальные.']),
  K('keyword_cluster','magnet','Кластеры ключевых фраз','группирует запросы нишы в темы под ролики','10 кластеров с приоритетом','low',25,.7,'доля поиска в трафике',
    ['Кластер 1: «свет для съёмки дома» → 3 уточняющих, сложность низкая, 2 ролика (инструкция, до/после).','Кластер 2: «микрофон для телефона» → сложность средняя, 1 обзор с замером.','Кластер 3: «как снять разговорный ролик» → сложность низкая, 2 ролика + плейлист.']),
  // Разведчик
  K('long_to_vertical','scout','Нарезка длинного в вертикальное','разбирает длинное видео на 4 отрывка с таймкодами','4 отрывка: таймкод, хук, подпись','medium',30,.9,'переходы Shorts → длинное',
    ['Отрывок 1: 00:02:10 → +43 с, хук «один кадр, который портит всё», ссылка на оригинал на 30-й секунде.','Отрывок 2: 00:07:55 → +38 с, хук «замер на 5000 ₽ и 500 ₽».','Отрывок 3: 00:12:20 → +51 с, хук «так не делают профи».','Отрывок 4: 00:18:02 → +35 с, хук «итоговый чек-лист в закрепе».']),
  K('cross_post_copy','scout','Адаптация под другую площадку','переписывает один контент под ритм второй площадки','комплект текстов для YT и TikTok','medium',15,.7,'охват на второй площадке',
    ['YouTube: «Свет из окна против кольцевого: замер» + 3 абзаца описания + таймкоды 0:00/1:40/4:12.','TikTok: «Проверил свет из окна и кольцо на одном сюжете. Разница не в цене» · 6 хэштегов.','Первая секунда: текст на экране, дублирующий хук (звук часто выключен).']),
  K('collab_pitch','scout','Питч на коллаборацию','ищет авторов того же уровня и пишет персональный питч','список авторов + 5 питчей','medium',40,.8,'прирост с чужой аудитории',
    ['Критерий: 0.5–2× твоего размера, живой отклик, пересекающаяся аудитория.','Идея: «обмен каналами на один сюжет» — ты снимаешь у себя, он у себя, монтаж общий.','Питч: 1) что смотрел и почему зашло 2) идея в одну фразу 3) что делаешь сам (съёмка, монтаж, кросс-пост) 4) дедлайн ответа 5 дней.']),
  K('comment_presence','scout','Присутствие в чужих комментариях','готовит осмысленные ответы под ролики соседей по нише','7 комментариев-мнений','medium',20,.55,'переходы из комментариев',
    ['«У меня после смены обложек CTR встал на 20% — пробовал и так и так, дело в читаемости на маленьком экране.»','«Спорно: длинное вступление работает, если в нём обещание результата, а не приветствие.»','Лимит: до 5 комментариев в день, без ссылок на свой канал, иначе платформа режет как спам.']),
  K('community_seed','scout','Посев в сообществах','подбирает площадки и пишет посты по их правилам','6 сообществ + 3 поста','high',35,.6,'внешние источники трафика',
    ['Места: 2 сабреддита по нише, 2 Telegram-чата, 1 форум, 1 Discord.','Пост 1: разбор ошибки новичков, ссылка второй строкой и только если спросят.','Запреты: не дублировать одно и то же в 5 мест за день, не игнорировать правила self-promo, не использовать бот-постинг.']),
  K('localization','scout','Локализация и дубли','готовит субтитры/озвучку и локализованные обложки','чек-лист + глоссарий','low',25,.5,'доля зарубежного трафика',
    ['Языки: английский (охват) и один региональный (конкуренция ниже).','Глоссарий: 15 терминов ниши с фиксированным переводом — иначе автоперевод разъедет смысл.','Вырезать: локальные шутки, которые не переведутся. Адаптировать хук: идиома → прямая выгода.']),
  // Ускоритель
  K('weekly_experiment','booster','Две гипотезы на неделю','формулирует эксперимент: гипотеза, метрика, выборка, вердикт','2 карточки экспериментов','low',25,.9,'скорость роста (нед/нед)',
    ['Э1: если перенести CTA с 5-й секунды на 40-ю, удержание вырастет, потому что просьба будет после пользы. Метрика: удержание на 60-й секунде, выборка 6 роликов, победа +3 п.п.','Э2: если заголовок начнётся с числа, CTR вырастет — появляется конкрета. Метрика: CTR показов, выборка 8 роликов, победа +10%.','Не трогаем: время публикации, длительность, монтаж — иначе не поймём, что сработало.']),
  K('winner_pattern','booster','Формула победителя','вытаскивает паттерн топ-5 роликов в шаблон','разбор + шаблон сценария','low',40,.95,'медианное удержание',
    ['Топ-5: хук-вопрос в первые 2 секунды, 3 блока пользы, финальный вопрос залу.','Низ: длинное вступление, 2 темы в ролике, просьба подписаться в начале.','Шаблон: обещание → почему я → 3 блока пользы с рестартом внимания → итог → вопрос.','Стоп-лист: извинения в начале, «в этом видео мы поговорим», отбивка дольше 2 сек.']),
  K('cadence_plan','booster','Ритм публикаций и буфер','считает устойчивую частоту и строит календарь','календарь на 14 дней','low',30,.8,'роликов в неделю без выгорания',
    ['Пн: съёмочный блок 2 часа, 2 ролика подряд, свет не менять.','Вт: монтаж черновика + правки по карте удержания.','Ср: публикация в 19:00, первый час — ответы на комментарии.','Буфер: 3 готовых ролика до старта недели + 1 «панический». В тяжёлую неделю режем количество, не качество.']),
  K('retrank_old','booster','Репаковка старого каталога','ищет ролики с хорошим удержанием и плохим CTR','5 кандидатов + новые пакеты','medium',30,.85,'просмотры старого каталога',
    ['Кандидат: удержание выше медианы, CTR ниже медианы, тема не сезонная, ролику от 3 месяцев.','Гипотеза 1: «Свет для съёмки дома» + обложка с лицом → придёт поисковая аудитория.','Когда вредно: истёкший тренд, устаревшие данные, коммерческое обещание в старом заголовке.','Действие: меняем обложку и заголовок, 7 дней описание не трогаем.']),
  K('retention_fix','booster','Карта удержания','ищет провалы на кривой и даёт список правок монтажа','cut-list по секундам','low',30,.85,'удержание',
    ['0–3 с: убрать приветствие, начинать с результата, добавить подпись на экране.','Смена темы: смена кадра + фраза «теперь главное».','Середина: вырезать паузы > 0.6 с, заменить объяснение на схему.','Правило на все ролики: новый визуальный стимул каждые 6–9 секунд.']),
  K('paid_boost_test','booster','Платный разгон с юнит-экономикой','считает тест рекламы и допустимую цену подписчика','план теста + таблица метрик','medium',35,.6,'стоимость подписчика',
    ['Бюджет: 3 дня × $50. Аудитории: интересы ниши, зрители похожего канала, ремаркетинг на досмотревших 75%.','Креативы: только победившие органически, вертикальный отрывок 20 сек.','Стоп: CTR < 1% за 1000 показов или цена подписчика > 2× исторической.','Важно: покупка просмотров и подписчиков — прямой бан. Здесь только своя реклама платформы.']),
  // Искра
  K('reply_drafts','spark','Ответы на комментарии','приоритизирует комментарии и пишет черновики в твоём тоне','20 ответов на 10 комментариях','medium',20,.8,'ответы ≤ 1 часа',
    ['Приоритет: вопрос по делу → развёрнутое мнение → критика → остальное.','Ответ на критику: признать факт, дать контекст, закрыть тему. Без оправданий.','Тон: спокойно, по делу. Никаких «спасибо за фидбек» — на 10-м комментарии это видно.','Ритм: первые 60 минут после публикации — до 20 ответов.']),
  K('cta_script','spark','Тайминг призывов','расставляет точки запроса действия внутри ролика','CTA-карта с таймкодами','medium',15,.7,'лайки/сохранения на ролик',
    ['CTA 1 на 40-й секунде, сразу после пользы: «если пригодилось — напиши, что оставил бы ещё».','CTA 2 на финале: «продолжение во втором ролике, он в закреплённом комментарии».','Нельзя: «подпишись, чтобы не пропустить» без причины, просьбы до 10-й секунды.']),
  K('poll_plan','spark','Опросы и вопрос дня','готовит сетку интерактивов на неделю','7 опросов + 3 челленджа','medium',20,.7,'вовлечённость в комьюнити',
    ['Опрос 1: «Какой формат снимать дальше?» — свет / звук / монтаж.','Опрос 2: «Правда, что смотришь без звука?» — да / нет / только ленту.','Челлендж: «покажи свою настройку за 15 секунд», ответный монтаж в пятницу.','Без «поставь лайк, если согласен» — это мусорный сигнал.']),
  K('ugc_loop','spark','Маховик фанатского контента','отбирает реакции зрителей и планирует ответы','правила сбора + 5 идей','medium',25,.6,'пользовательский контент',
    ['Что просим: 15-секундная реакция или повтор приёма, хэштег автора.','Как отвечаем: duet/stitch в течение 48 часов, имя автора в кадре.','Юридика: чужую нарезку без разрешения не берём, музыка — только из библиотеки платформы.']),
  K('live_event_plan','spark','Live-событие','план прямого эфира с анонсами и разгоном чата','рундаун + тексты анонсов','medium',40,.65,'активность в эфире',
    ['Рундаун 40 минут: 0–5 тема, 5–15 разбор, 15–25 ответы, 25–35 практика, 35–40 итоги и анонс.','Просадка зрителей: смена блока на 60-секундный вопрос залу, не затягивать монолог.','После: 5 вертикальных нарезок за 24 часа, таймкоды в описании.']),
  K('moderation_rules','spark','Мягкая модерация','настраивает фильтры и шаблоны реакций','список фильтров + 5 шаблонов','high',25,.5,'тональность комьюнити',
    ['Автоскрытие: оскорбления личностей, спам-ссылки, угрозы.','Удаляем всегда: призывы к насилию, личные данные зрителей.','Оставляем: жёсткую критику контента и спор по существу — это сигнал.','Шаблон хейту: «Принято. Если есть аргумент — слушаю в комментариях, дальше не продолжаем». Одно сообщение, тема закрыта.','Запрещено: масс-репорты конкурентов, боты-ответы, взаимные накрутки.']),
];

const PLAYBOOKS = [
  {id:'magnet.packaging', agent:'magnet', title:'Упаковка для поиска', cadence:'каждый новый ролик', summary:'Заголовки, описания, обложки — всё, что отвечает за клик.', kinds:['seo_rewrite','thumbnail_ab','keyword_cluster']},
  {id:'magnet.funnel', agent:'magnet', title:'Воронка подписки', cadence:'1 раз в неделю', summary:'Где зритель уходит и как добрать подписчика без просьб.', kinds:['funnel_audit','series_plan']},
  {id:'magnet.trend', agent:'magnet', title:'Трендовое окно', cadence:'каждый день, 15 минут', summary:'Ловим растущие форматы, пока окно открыто 24–48 часов.', kinds:['trend_jack']},
  {id:'scout.recycling', agent:'scout', title:'Один материал — пять площадок', cadence:'после каждого длинного ролика', summary:'Нарезка и адаптация того, что уже снято.', kinds:['long_to_vertical','cross_post_copy','localization']},
  {id:'scout.alliances', agent:'scout', title:'Чужая аудитория', cadence:'2 касания в неделю', summary:'Коллаборации, комментарии, посевы.', kinds:['collab_pitch','comment_presence','community_seed']},
  {id:'booster.experiments', agent:'booster', title:'Цикл экспериментов', cadence:'понедельник', summary:'Две гипотезы в неделю, замер, вердикт, масштабирование.', kinds:['weekly_experiment','winner_pattern']},
  {id:'booster.cadence', agent:'booster', title:'Ритм и буфер', cadence:'воскресенье', summary:'Частота публикаций, которую можно держать месяцами.', kinds:['cadence_plan','retention_fix']},
  {id:'booster.catalog', agent:'booster', title:'Оживление каталога', cadence:'1 раз в 2 недели', summary:'Старые ролики с хорошим удержанием получают новый клик.', kinds:['retrank_old','paid_boost_test']},
  {id:'spark.first_hour', agent:'spark', title:'Первый час', cadence:'в день публикации', summary:'Ответы, CTA и опросы в первые 60 минут.', kinds:['reply_drafts','cta_script','poll_plan']},
  {id:'spark.community', agent:'spark', title:'Комьюнити-маховик', cadence:'1 активация в неделю', summary:'UGC, эфиры и модерация, которая держит тон.', kinds:['ugc_loop','live_event_plan','moderation_rules']},
];

const NEVER = [
  'не накручивает просмотры, подписчиков, лайки и комментарии',
  'не использует ботов, sub4sub, масс-фолловинг и платные «активности»',
  'не публикует и не комментирует от имени автора',
  'не отправляет автоматические жалобы на чужие каналы',
  'не обещает точные цифры роста',
];

/* ── состояние ── */
const SHIFT_START = 9*60, SHIFT_END = 18*60;
const S = {
  phase:'idle', clock:SHIFT_START, day:new Date().toISOString().slice(0,10),
  speed:2, tasks:[], events:[], artifacts:[], queue:[], report:null,
  runtime:Object.fromEntries(AGENTS.map(a=>[a.key,{busy:false,task:'',progress:0,done:0,wait:0,out:0,last:'',msg:'ожидает старта'}])),
  cfg:Object.fromEntries(AGENTS.map(a=>[a.key,{enabled:true,intensity:3,autonomy:'prepare',playbooks:PLAYBOOKS.filter(p=>p.agent===a.key).map(p=>p.id)}])),
  tab:'shift', openAgent:null, filter:'approval', expanded:{},
  profile:{youtube:'UCd3moKe7f2',tiktok:'@workday.channel',niche:'съёмка и монтаж на телефон',audience:'новички 22–38, хотят вести канал как хобби',tone:'спокойно, по делу, с юмором без иронии над зрителем',cadence:4},
  goals:{subs:350,posts:5,retention:45,er:6},
  llm:{enabled:false,base:'https://api.openai.com/v1',key:'',model:'gpt-4o-mini'},
};

const clock = m => String(Math.floor(m/60)).padStart(2,'0')+':'+String(m%60).padStart(2,'0');
const byId = id => ACTIONS.find(a=>a.id===id);
const agent = k => AGENTS.find(a=>a.key===k);
const rnd = (n) => Math.floor(Math.random()*n);
let uid=0;

function log(agentKey, kind, text){
  S.events.unshift({at:Date.now()+uid++, c:S.clock, a:agentKey, kind, text});
  S.events = S.events.slice(0,120);
}
function toast(text){
  const el=document.getElementById('toast'); el.textContent=text; el.classList.add('on');
  clearTimeout(el._t); el._t=setTimeout(()=>el.classList.remove('on'),2600);
}

/* ── планирование смены ── */
function plan(){
  S.tasks=[];
  AGENTS.forEach(a=>{
    const cfg=S.cfg[a.key];
    if(!cfg.enabled){ log(a.key,'warn','агент выключен, смена без задач'); return; }
    const kinds = PLAYBOOKS.filter(p=>cfg.playbooks.includes(p.id)).flatMap(p=>p.kinds).map(byId).filter(Boolean);
    if(!kinds.length){ log(a.key,'warn','нет включённых плейбуков'); return; }
    const wanted = Math.min(2 + cfg.intensity, cfg.dailyLimit ?? 12);
    const ordered = [...kinds].sort((x,y)=>(y.impact*y.effort)-(x.impact*x.effort));
    for(let i=0;i<wanted;i++){
      const kind = ordered[i % ordered.length];
      let slot = SHIFT_START + Math.floor((SHIFT_END-SHIFT_START)/8) * i + rnd(25) - 12;
      slot = Math.max(SHIFT_START, Math.min(SHIFT_END - 30, slot));
      S.tasks.push({id:`d-${a.key}-${i}`, agent:a.key, kind:kind.id, slot, status:'planned', progress:0, out:null, spent:0});
    }
    log(a.key,'plan',`план: ${wanted} задач · ${new Set(kinds.map(k=>k.title)).size} типов работ`);
  });
}

/* ── исполнение задачи ── */
function finish(task){
  const kind = byId(task.kind);
  const art = {id:'art-'+task.id, task:task.id, agent:task.agent, kind:task.kind, at:S.clock, body:kind.output.join('\n')};
  S.artifacts.unshift(art); task.out = art.id;
  const needApproval = kind.risk!=='low';
  task.status = needApproval ? 'approval' : 'done';
  const r = S.runtime[task.agent];
  r.busy=false; r.task=''; r.progress=1; r.out++;
  if(needApproval){ r.wait++; r.msg='ждёт твоего одобрения'; log(task.agent,'approval',`готово «${kind.title}» · риск ${kind.risk==='high'?'высокий':'средний'} → жду OK (слот ${clock(task.slot)})`); }
  else { r.done++; r.msg='задача закрыта'; log(task.agent,'done',`готово «${kind.title}» → ${kind.out}`); }
  r.last = kind.output[0].replace(/[«»]/g,'').slice(0,150);
  if(r.done && r.out%4===0) S.metricsTick?.();
}

function tick(){
  if(S.phase!=='working') return;
  S.clock += 6;
  if(S.clock>=SHIFT_END){ report(); render(); return; }
  AGENTS.forEach(a=>{
    if(!S.cfg[a.key].enabled) return;
    const r=S.runtime[a.key];
    if(r.busy){
      const t=S.tasks.find(x=>x.id===r.taskId);
      if(!t){ r.busy=false; return; }
      const kind=byId(t.kind);
      const speed=0.35+0.14*(S.cfg[a.key].intensity-1);
      t.progress=Math.min(1,t.progress+speed); t.spent+=6;
      r.progress=t.progress;
      if(t.progress>=1) finish(t);
      return;
    }
    const next=S.tasks.find(x=>x.agent===a.key && x.status==='planned' && x.slot<=S.clock);
    if(!next) return;
    const kind=byId(next.kind);
    next.status='running';
    Object.assign(r,{busy:true,taskId:next.id,task:kind.title,progress:0,msg:`делает «${kind.title}»`});
    log(a.key,'start',`взял «${kind.title}» (${clock(S.clock)}) · ~${kind.effort} мин`);
  });
  render();
}

function report(){
  clearInterval(S.timer); S.timer=null; S.phase='finished';
  const per = AGENTS.map(a=>{
    const r=S.runtime[a.key];
    const mine=S.tasks.filter(t=>t.agent===a.key && t.status!=='skipped');
    const impact=mine.filter(t=>t.status==='done'||t.status==='approval').reduce((s,t)=>s+byId(t.kind).impact,0);
    const best=mine.sort((x,y)=>byId(y.kind).impact-byId(x.kind).impact)[0];
    return {agent:a.key, done:r.done, wait:r.wait, out:r.out, score:Math.min(100,Math.round(impact/4*100)), hi:best?byId(best.kind).title:'—'};
  });
  S.report={day:S.day, per};
  log(null,'end',`18:00 · смена закрыта: ${S.tasks.filter(t=>t.status==='done').length} задач готово, ${S.tasks.filter(t=>t.status==='approval').length} ждут одобрения`);
}

/* ── действия пользователя ── */
function approve(id){
  const t=S.tasks.find(x=>x.id===id); if(!t) return;
  const kind=byId(t.kind);
  t.status='queued'; S.runtime[t.agent].wait=Math.max(0,S.runtime[t.agent].wait-1);
  S.queue.unshift({id:'p'+(uid++), task:t.id, agent:t.agent, kind:t.kind, slot:t.slot, state:'ready'});
  log(t.agent,'done',`одобрено → очередь публикации в ${clock(t.slot)} · ${t.agent==='scout'?'TikTok':'YouTube'}`);
  toast('Пакет в очереди. Публикуешь ты сам — у приложения нет прав на запись');
  render();
}
function skip(id){
  const t=S.tasks.find(x=>x.id===id); if(!t) return;
  t.status='skipped'; if(S.runtime[t.agent].busy && S.runtime[t.agent].taskId===id){S.runtime[t.agent].busy=false;S.runtime[t.agent].progress=0;}
  log(t.agent,'warn','задача убрана из плана дня'); render();
}
function published(i){ const q=S.queue.find(x=>x.id===i); if(q){q.state='published'; log(q.agent,'done','отметил публикацию — агент учтёт это в следующих замерах');} render(); }

function startShift(){
  if(S.phase==='paused'){ S.phase='working'; S.timer=setInterval(tick,900/S.speed); log(null,'info','продолжаем смену'); render(); return; }
  Object.values(S.runtime).forEach(r=>Object.assign(r,{busy:false,task:'',progress:0,done:0,wait:0,out:0,last:'',msg:'планирую день'}));
  S.artifacts=[]; S.queue=[]; S.events=[]; S.report=null; S.clock=SHIFT_START;
  S.phase='planning'; render();
  setTimeout(()=>{ log(null,'start',`смена ${clock(S.clock)} · набираем план`); plan(); S.phase='working'; S.timer=setInterval(tick,900/S.speed); render(); },450);
}
function pauseShift(){ if(S.phase!=='working')return; clearInterval(S.timer); S.timer=null; S.phase='paused'; log(null,'info','смена на паузе'); render(); }
function stopShift(){ clearInterval(S.timer); S.timer=null; S.phase='idle'; S.clock=SHIFT_START; render(); }

/* ═══════════════════════════════════════════════════════════════════
   Авторизация. Зеркалит Kotlin-слой data/auth: Google и TikTok — OAuth
   с PKCE и редиректом на кастомную схему, логин/пароль — Firebase, если задан
   API-ключ, иначе локальный аккаунт устройства. В браузере нет ни браузера-вкладки,
   ни PBKDF2, поэтому здесь имитируются ровно те же проверки, что в коде приложения.
   ═══════════════════════════════════════════════════════════════════ */
const A = (() => {
  const READ_ONLY = {
    google: ['youtube.readonly', 'yt-analytics.readonly'],
    tiktok: ['user.info.basic', 'video.list'],
  };
  const BANNED = ['upload', 'force-ssl', 'insert', 'update', 'delete', 'moderation', 'publish'];
  let unlocked = false;
  let pending = null;

  const state = () => S.auth;

  function needsAuth() { const a = state(); return !(a.session.links.length || a.session.email || a.session.guest); }

  function validateEmail(email) { return /.+@.+\..+|.+@.+/.test(email.trim()) && email.trim().length > 5; }
  function validatePassword(pw) { return typeof pw === 'string' && pw.length >= 6; }

  // тот же набор проверок, что в AuthRepository.validate/register
  function checkCredentials(email, password, confirm, mode) {
    const errors = [];
    if (!validateEmail(email)) errors.push('Нужен корректный email');
    if (!validatePassword(password)) errors.push('Пароль от 6 символов');
    if (mode === 'register' && password !== confirm) errors.push('Пароли не совпадают');
    if (mode === 'register' && state().session.email && state().session.email !== email.trim().toLowerCase()) {
      if (state().clients.firebase) errors.push('Такой email уже зарегистрирован');
    }
    return errors;
  }

  // «хеш» в прототипе — не криптография, а имитация: пароль нигде не сохраняется
  function fakeHash(pw, salt) { let h = 2166136261; const src = salt + pw + salt;
    for (let i = 0; i < src.length; i++) { h ^= src.charCodeAt(i); h = Math.imul(h, 16777619); }
    return (h >>> 0).toString(16).padStart(8, '0').repeat(8).slice(0, 64); }

  function register(email, password, confirm) {
    const errors = checkCredentials(email, password, confirm, 'register');
    if (errors.length) return { ok: false, errors };
    const salt = Math.random().toString(36).slice(2, 10);
    const a = state();
    a.session.email = email.trim().toLowerCase();
    a.session.passwordSalt = salt;
    a.session.passwordHash = fakeHash(password, salt);
    a.session.lockEnabled = true;
    a.session.guest = false;
    a.backend = a.clients.firebase ? 'firebase' : 'local';
    log(null, 'info', a.backend === 'firebase' ? 'Аккаунт создан в Firebase' : 'Пароль установлен, приложение под замком');
    return { ok: true, lock: true };
  }

  function signIn(email, password) {
    const a = state();
    const errors = checkCredentials(email, password, password, 'signin').filter(e => e !== 'Пароли не совпадают');
    if (errors.length) return { ok: false, errors };
    if (!a.session.passwordHash) return { ok: false, errors: ['Аккаунта на этом устройстве нет — зарегистрируйся'] };
    if (a.session.email !== email.trim().toLowerCase()) return { ok: false, errors: ['Почта не совпадает с указанной при регистрации'] };
    if (fakeHash(password, a.session.passwordSalt) !== a.session.passwordHash) return { ok: false, errors: ['Неверный пароль'] };
    a.session.guest = false;
    return { ok: true };
  }

  function beginLink(provider) {
    const a = state();
    const id = provider === 'google' ? a.clients.google : a.clients.tiktok;
    if (!id) return { ok: false, error: provider === 'google' ? 'В настройках не указан Google Client ID' : 'В настройках не указан TikTok Client Key' };
    pending = { provider, verifier: Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2), state: Math.random().toString(36).slice(2, 12) };
    const scopes = READ_ONLY[provider];
    if (scopes.some(s => BANNED.some(b => s.includes(b)))) return { ok: false, error: 'внутренняя ошибка: запрещённый scope' };
    const url = (provider === 'google' ? 'https://accounts.google.com/o/oauth2/v2/auth' : 'https://www.tiktok.com/v2/auth/authorize/')
      + '?client_' + (provider === 'google' ? 'id' : 'key') + '=' + encodeURIComponent(id)
      + '&redirect_uri=' + encodeURIComponent(a.clients.redirect)
      // у Google scope разделяются пробелом, у TikTok — запятой: перепутать значит получить отказ
      + '&response_type=code&scope=' + encodeURIComponent(scopes.join(provider === 'tiktok' ? ',' : ' '))
      + '&code_challenge_method=S256&state=' + pending.state;
    return { ok: true, url, scopes };
  }

  /** Симуляция возврата из браузера: state обязательно должен совпасть. */
  function completeLink(queryState, opts = {}) {
    const a = state();
    if (!pending) return { ok: false, error: 'Авторизация не начата или устарела (лимит 5 минут)' };
    if (opts.error) { const e = 'отказ авторизации: ' + opts.error; pending = null; return { ok: false, error: e }; }
    if (queryState !== pending.state) return { ok: false, error: 'state не совпал — редирект отклонён' };
    if (!opts.code) return { ok: false, error: 'в редиректе нет code' };
    const provider = pending.provider;
    pending = null;
    const link = {
      provider,
      subject: opts.subject || (provider === 'google' ? 'g-' + Math.random().toString(36).slice(2, 9) : 'tt-' + Math.random().toString(36).slice(2, 9)),
      name: opts.name || (provider === 'google' ? 'Канал автора' : '@workday.channel'),
      email: provider === 'google' ? (opts.email || 'author@gmail.com') : '',
      scopes: READ_ONLY[provider],
      expiresAt: Date.now() + 3600 * 1000,
      canRefresh: true,
      followers: opts.followers || 0,
    };
    a.session.links = a.session.links.filter(l => l.provider !== provider).concat([link]);
    a.session.guest = false;
    if (provider === 'google' && link.followers) S.profile.youtube = link.subject;
    log(null, 'done', provider === 'google' ? `YouTube подключён: ${link.followers.toLocaleString('ru-RU')} подписчиков` : `TikTok подключён${link.followers ? ': ' + link.followers.toLocaleString('ru-RU') + ' подписчиков' : ' (stats-скоуп не одобрен — цифр нет)'}`);
    return { ok: true, link };
  }

  function revoke(provider) {
    const a = state();
    a.session.links = a.session.links.filter(l => l.provider !== provider);
    log(null, 'warn', provider === 'google' ? 'Google отвязан, токен отозван' : 'TikTok отвязан');
  }

  function expiryText(link) {
    if (!link.expiresAt) return 'без срока';
    const left = Math.round((link.expiresAt - Date.now()) / 60000);
    if (left <= 0) return link.canRefresh ? 'токен истёк, обновлю сам' : 'токен истёк — войди заново';
    return `действует ещё ${left} мин`;
  }

  return { needsAuth, validateEmail, validatePassword, checkCredentials, register, signIn, beginLink, completeLink, revoke, expiryText,
           unlock: (pw) => { const a = state(); if (!a.session.passwordHash) { unlocked = true; return true; }
                             if (fakeHash(pw, a.session.passwordSalt) === a.session.passwordHash) { unlocked = true; return true; } return false; },
           isLocked: () => state().session.lockEnabled && !unlocked,
           forceUnlock: () => { unlocked = true; }, scopesFor: (p) => READ_ONLY[p].slice(), state };
})();

S.auth = { session: { links: [], email: '', guest: false, lockEnabled: false, passwordHash: '', passwordSalt: '' },
           clients: { google: '', tiktok: '', firebase: '', redirect: 'workdayauth://oauth2callback' }, backend: 'local' };

function viewAuth() {
  const a = S.auth;
  const form = A_FORM;
  const err = AUTH_ERRORS.length ? `<div class="panel" style="background:#26141a;border-color:#5b2635">${AUTH_ERRORS.map(e => `<div class="sub" style="color:#ffb3c1">• ${e}</div>`).join('')}</div>` : '';
  return `<div class="sec" style="margin-top:10px">Work Day</div>
  <div style="font-size:21px;font-weight:800;letter-spacing:-.4px">Смена из четырёх AI-агентов</div>
  <div class="sub" style="margin:5px 0 14px">Прирост, привлечение, ускорение и активность для YouTube и TikTok. Вход не обязателен: без привязанных площадок агенты работают на демо-данных.</div>
  ${err}
  <div class="panel">
    <div class="h" style="font-size:15px">Войти, чтобы видеть свои цифры</div>
    ${[['google','▶','Google','канал, просмотры, удержание и источники трафика · только чтение','#ff4e45'],
        ['tiktok','♪','TikTok','подписчики, лайки, список роликов · по одобренным scope','#25f4ee']].map(([k,icon,t,d,col])=>{
      const ready = k==='google' ? !!a.clients.google : !!a.clients.tiktok;
      const connected = a.session.links.some(l=>l.provider===k);
      return `<div class="playbook" style="border:0;padding:8px 0">
        <div class="ava" style="background:${col}22;color:${col}">${icon}</div>
        <div class="grow"><div style="font-weight:700;font-size:14px">${t}</div><div class="sub" style="color:${ready?'var(--t2)':'var(--danger)'}">${ready?d:'нужен '+(k==='google'?'Google Client ID':'TikTok Client Key')+' в настройках'}</div></div>
        <button class="pill" style="${connected?'background:var(--ok);color:#06231a':ready?'background:'+col:''}" ${connected||!ready?'disabled':''} onclick="linkStart('${k}')">${connected?'подключено':'подключить'}</button>
      </div>`}).join('')}
    <div class="sub" style="margin-top:6px">Права на публикацию, удаление и управление комментариями приложение не запрашивает — и не попросит: публиковать будешь сам.</div>
  </div>

  <div class="panel">
    <div class="row sb"><div class="h" style="font-size:15px">Логин и пароль</div>
      <span class="tag" style="color:var(--mint)">${a.clients.firebase?'Firebase Auth':'локальный режим'}</span></div>
    <div class="sub" style="margin-top:5px">${a.clients.firebase
      ? 'Аккаунт в твоём Firebase-проекте: пароль не хранится на устройстве, настройки переносимы.'
      : 'Своего сервера нет, поэтому аккаунт создаётся на устройстве: пароль превращается в PBKDF2-хеш (210 000 итераций, случайная соль) и проверяется офлайн. Это замок на приложение, а не переносимый аккаунт.'}</div>
    <div class="chips" style="margin-top:11px">${[['signin','Вход'],['register','Регистрация'],['reset','Забыли?']].map(([k,l])=>`<button class="pill ${form===k?'on':''}" style="${form===k?'background:var(--violet)':''}" onclick="A_FORM='${k}';AUTH_ERRORS=[];render()">${l}</button>`).join('')}</div>
    <label class="lbl">Почта</label><input class="field" id="f_email" value="${A_EMAIL}" oninput="A_EMAIL=this.value">
    ${form!=='reset'?`<label class="lbl">Пароль</label><input class="field" id="f_pw" type="password" value="${A_PW}" oninput="A_PW=this.value">`:''}
    ${form==='register'?`<label class="lbl">Повтори пароль</label><input class="field" id="f_pw2" type="password" value="${A_PW2}" oninput="A_PW2=this.value">`:''}
    <div class="row" style="margin-top:12px">
      ${form==='reset'
        ? `<button class="btn" onclick="doReset()">Письмо для сброса</button>`
        : `<button class="btn" onclick="${form==='register'?'doRegister()':'doSignIn()'}">${form==='register'?'Создать аккаунт':'Войти'}</button>`}
      <button class="btn ghost" onclick="S.auth.session.guest=true;render()">Без входа</button>
    </div>
  </div>`;
}

let A_FORM='signin', A_EMAIL='', A_PW='', A_PW2='', AUTH_ERRORS=[];

function doRegister(){ const r=A.register(A_EMAIL,A_PW,A_PW2); AUTH_ERRORS=r.ok?[]:r.errors; if(r.ok){A_PW='';A_PW2='';toast('Аккаунт создан · приложение под замком');} render(); }
function doSignIn(){ const r=A.signIn(A_EMAIL,A_PW); AUTH_ERRORS=r.ok?[]:r.errors; if(r.ok){A_PW='';A.forceUnlock();render();} else render(); }
function doReset(){ if(!S.auth.clients.firebase){AUTH_ERRORS=['Сброс по почте доступен, когда подключён Firebase'];return render();} toast('Письмо для сброса отправлено'); }
function linkStart(provider){
  const r = A.beginLink(provider);
  if(!r.ok){ AUTH_ERRORS=[r.error]; return render(); }
  toast('Открываю страницу согласия '+(provider==='google'?'Google':'TikTok')+' · редирект '+S.auth.clients.redirect);
  const state = new URL(r.url).searchParams.get('state');
  setTimeout(()=>{
    const followers = provider==='google' ? 18420 + Math.floor(Math.random()*900) : 27150 + Math.floor(Math.random()*1500);
    const back = A.completeLink(state, { code:'sim-'+Math.random().toString(36).slice(2,8), followers, name: provider==='google'?'Канал съёмки на телефон':'@workday.channel' });
    if(!back.ok) AUTH_ERRORS=[back.error];
    render();
  }, 700);
}
function viewLock(){
  return `<div class="panel" style="margin-top:80px">
    <div class="h">Work Day</div>
    <div class="sub">${S.auth.session.email?'Приложение защищено паролем · '+S.auth.session.email:'Приложение защищено паролем'}</div>
    <label class="lbl">Пароль</label><input class="field" type="password" id="lock_pw" oninput="LOCK_PW=this.value">
    <div class="row" style="margin-top:12px"><button class="btn" onclick="tryUnlock()">Разблокировать</button></div>
    <div class="sub" style="margin-top:9px">Проверка локальным PBKDF2-хешем, поэтому работает без сети. Восстановить пароль нельзя — только сброс данных.</div>
  </div>`;
}
let LOCK_PW='';
function tryUnlock(){ if(A.unlock(LOCK_PW)){LOCK_PW='';render();} else toast('Пароль не подошёл'); }

function viewAccount(){
  const a=S.auth;
  return `<div class="sec" style="margin-top:4px">Аккаунт и доступы</div>
  <div class="panel"><div class="sub">Токены лежат в Android Keystore (в прототипе — в памяти вкладки). В выгрузку настроек и в логи они не попадают.</div>
  ${a.session.links.length? a.session.links.map(l=>`<div class="playbook" style="border-bottom:1px dashed #232a3d">
      <div class="ava" style="width:30px;height:30px;font-size:14px;background:${l.provider==='google'?'#ff4e4522':'#25f4ee22'}">${l.provider==='google'?'▶':'♪'}</div>
      <div class="grow"><div style="font-weight:700;font-size:13.5px">${l.provider==='google'?'Google':'TikTok'} · ${l.name}</div>
      <div class="sub">${[l.email, 'scope: '+l.scopes.join(' '), A.expiryText(l), l.followers?('подписчиков: '+l.followers.toLocaleString('ru-RU')):''].filter(Boolean).join(' · ')}</div></div>
      <button class="pill" onclick="A.revoke('${l.provider}');render()">Отвязать</button></div>`).join('')
    : `<div class="sub" style="margin-top:8px">Ни один провайдер не привязан. Агенты работают на демо-данных и офлайн-движке.</div>`}
  <div class="chips" style="margin-top:11px">
    <button class="pill" onclick="linkStart('google')">Подключить Google</button>
    <button class="pill" onclick="linkStart('tiktok')">Подключить TikTok</button>
    <button class="pill" onclick="S.auth={...S.auth,session:{links:[],email:'',guest:false,lockEnabled:false,passwordHash:'',passwordSalt:''}};render()">Выйти и отвязать всё</button>
  </div></div>
  <div class="sec">Клиенты авторизации</div>
  <div class="panel"><div class="sub">Work Day — публичный клиент: секрета приложения у него нет и быть не может. Google настраивается клиентом «Android» (пакет + SHA-1 сборки), TikTok — Client Key из твоего приложения в TikTok for Developers с тем же redirect.</div>
    <label class="lbl">Google Client ID</label><input class="field" value="${a.clients.google}" oninput="S.auth.clients.google=this.value" placeholder="xxxx.apps.googleusercontent.com">
    <label class="lbl">TikTok Client Key</label><input class="field" value="${a.clients.tiktok}" oninput="S.auth.clients.tiktok=this.value" placeholder="aw…">
    <label class="lbl">Firebase Web API Key</label><input class="field" value="${a.clients.firebase}" oninput="S.auth.clients.firebase=this.value" placeholder="AIza…">
    <label class="lbl">Redirect URI</label><input class="field" value="${a.clients.redirect}" oninput="S.auth.clients.redirect=this.value">
    <div class="sub" style="margin-top:8px">В прототипе поля не сохраняются; в приложении — да, на устройстве.</div>
  </div>
  <div class="sec">Замок на приложении</div>
  <div class="panel"><div class="row"><div class="grow"><div style="font-weight:700;font-size:14px">${a.session.lockEnabled?'Включён':'Выключен'}</div>
    <div class="sub">${a.session.email?'аккаунт '+a.session.email:'аккаунт не заведён'} · режим ${a.backend==='firebase'?'Firebase':'локальный хеш'}</div></div>
    <div class="switch ${a.session.lockEnabled?'on':''}" onclick="S.auth.session.lockEnabled=!S.auth.session.lockEnabled;render()"><i></i></div></div>
    <div class="sub" style="margin-top:8px">Даже если аккаунт заведён в Firebase, пароль устройства сверяется локальным хешем: в метро запрос к Firebase не должен быть условием входа в свои заметки.</div></div>`;
}

/* ═══ RENDER ═══ */
const TABS=[['shift','Смена','M4 5h16v14H4z M4 9h16'],['agents','Агенты','M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8m-7 8a7 7 0 0 1 14 0'],['tasks','Задачи','M5 7h14M5 12h14M5 17h9'],['growth','Рост','M4 19V9m5 10V5m5 14v-7m5 7V8'],['account','Аккаунт','M9 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8m-6 8a6 6 0 0 1 12 0M17 8h4m-2-2v4'],['settings','Настройки','M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6m7-3a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.3 1a7 7 0 0 0-1.7-1L12.5 2h-4l-.4 2.6a7 7 0 0 0-1.7 1l-2.3-1-2 3.4L4.1 9.5a7 7 0 0 0 0 2L2.1 13l2 3.4 2.3-1a7 7 0 0 0 1.7 1l.4 2.6h4l.4-2.6a7 7 0 0 0 1.7-1l2.3 1 2-3.4-2-1.5c.1-.3.1-.7.1-1z']];

function render(){
  document.getElementById('sbClock').textContent=clock(S.clock);
  if (A.isLocked() || A.needsAuth()) {
    document.getElementById('tabbar').innerHTML='';
    document.getElementById('screen').innerHTML = A.isLocked() ? viewLock() : viewAuth();
    return;
  }
  const pending=S.tasks.filter(t=>t.status==='approval').length;
  document.getElementById('tabbar').innerHTML = TABS.map(([k,label,path])=>
    `<button class="${S.tab===k?'on':''}" onclick="S.tab='${k}';render()"><span style="position:relative">${pending&&k==='tasks'?`<span class="badge">${pending}</span>`:''}<svg viewBox="0 0 24 24"><path d="${path}"/></svg></span>${label}</button>`).join('');
  const el=document.getElementById('screen');
  el.innerHTML = ({shift:viewShift,agents:viewAgents,tasks:viewTasks,growth:viewGrowth,account:viewAccount,settings:viewSettings})[S.tab]();
}

function phaseLabel(){return {idle:'смена не идёт',planning:'распределяем задачи',working:'идёт смена',paused:'пауза',finished:'смена закрыта'}[S.phase]}
function ctrl(){
  const running=S.phase==='working';
  return `<div class="row" style="margin-top:12px">
    <button class="btn" onclick="${running?'':'startShift()'}" ${running?'disabled':''}>${S.phase==='paused'?'Продолжить':running?'Смена идёт':'Начать смену'}</button>
    <button class="btn ghost" onclick="pauseShift()" ${running?'':'disabled'}>Пауза</button>
    <button class="btn ghost" onclick="stopShift()" ${S.phase==='idle'?'disabled':''}>Стоп</button>
    <div class="grow"></div>
    <div class="chips">${[1,2,4,8].map(s=>`<button class="pill ${S.speed===s?'on':''}" style="${S.speed===s?'background:var(--violet)':''}" onclick="S.speed=${s};if(S.timer){clearInterval(S.timer);S.timer=setInterval(tick,900/${s})}render()">×${s}</button>`).join('')}</div>
  </div>`;
}

function viewShift(){
  const done=S.tasks.filter(t=>t.status==='done'||t.status==='queued').length;
  const appr=S.tasks.filter(t=>t.status==='approval').length;
  const pct=Math.round((S.clock-SHIFT_START)/(SHIFT_END-SHIFT_START)*100);
  return `
  <div class="panel acc">
    <div class="row"><div class="grow">
      <div style="font-size:20px;font-weight:800;letter-spacing:-.4px">Work Day</div>
      <div class="sub">${S.day} · ${phaseLabel()} · ${clock(S.clock)}–${clock(SHIFT_END)}</div>
    </div><div style="font-size:22px;color:${running()?  'var(--ok)':'var(--t3)'}">${running()?'●':'○'}</div></div>
    <div style="height:12px"></div>
    <div class="bar"><i style="width:${Math.max(0,Math.min(100,pct))}%;background:var(--violet)"></i></div>
    <div class="row sb" style="margin-top:5px"><span class="sub mono">${clock(SHIFT_START)}</span><span class="sub">рабочий день ${pct}%</span><span class="sub mono">${clock(SHIFT_END)}</span></div>
    ${ctrl()}
  </div>

  <div class="panel soft" style="display:flex;justify-content:space-between;text-align:left">
    <div class="stat">задач<b>${done}/${S.tasks.length}</b></div>
    <div class="stat">одобрение<b style="color:${appr?'var(--sun)':'var(--t1)'}">${appr}</b></div>
    <div class="stat">материалы<b>${S.artifacts.length}</b></div>
    <div class="stat">очередь<b style="color:var(--mint)">${S.queue.length}</b></div>
  </div>

  <div class="sec">Агенты в смене</div>
  ${AGENTS.map(a=>{
    const r=S.runtime[a.key], cur=S.tasks.find(t=>t.id===r.taskId&&t.status==='running');
    const kind=cur?byId(cur.kind):null;
    return `<div class="panel" style="${r.busy?`border-color:${a.accent}88`:''}">
      <div class="row"><div class="ava" style="background:${a.accent}22">${a.emoji}</div>
        <div class="grow"><div style="font-weight:700">${a.name}</div><div class="sub" style="color:${a.accent}">${a.dir}</div></div>
        <span class="tag" style="color:${r.busy?a.accent:'var(--t3)'}">${r.busy?'работает':(r.done+r.wait?'готово':'ждёт')}</span></div>
      <div class="sub" style="margin:8px 0 7px">${kind?`«${kind.title}» · ${kind.what}`:r.msg}</div>
      <div class="bar"><i style="width:${Math.round(r.progress*100)}%;background:${a.accent}"></i></div>
      <div class="row sb" style="margin-top:8px"><span class="sub">закрыто ${r.done}</span><span class="sub" style="color:${r.wait?'var(--sun)':'var(--t3)'}">на одобрении ${r.wait}</span><span class="sub">материалов ${r.out}</span></div>
      ${r.last?`<div class="task out" style="margin-top:10px">${r.last}…</div>`:''}
    </div>`;
  }).join('')}

  ${S.report?`<div class="sec">Отчёт смены</div>
  <div class="panel soft">${S.report.per.map(p=>`<div class="row sb" style="padding:5px 0"><span>${agent(p.agent).emoji} ${agent(p.agent).name}</span><span class="sub">${p.done} готово · ${p.wait} ждут · оценка <b style="color:${agent(p.agent).accent}">${p.score}</b></span></div>`).join('')}
    <div class="sub" style="margin-top:9px">Публикации агенты не делают — только пакеты и напоминания в слоты. Итог по метрикам смотришь через 7–14 дней.</div></div>`:''}

  <div class="sec">Лента смены</div>
  ${S.events.length?`<div class="feed">${S.events.slice(0,40).map(e=>`<div class="ev ${e.kind==='warn'?'warn':e.kind==='approval'?'approval':e.kind==='done'?'done':''}">
      <span class="c mono">${clock(e.c)}</span><span>${e.a?agent(e.a).emoji:'•'}</span><span class="grow">${e.text}</span></div>`).join('')}</div>`
    :`<div class="panel"><div class="sub">Нажми «Начать смену» — здесь появится, что именно делают агенты: план, взятые задачи, готовые материалы и точки, где нужно твоё решение.</div></div>`}
  <div class="sub" style="margin:14px 2px">Агенты не публикуют и не накручивают активность. Всё публичное проходит через тебя.</div>`;
}
const running=()=>S.phase==='working';

function viewAgents(){
  return `<div class="sec" style="margin-top:4px">Четыре агента</div>
  <div class="sub" style="margin:-2px 2px 10px">Каждый отвечает за одно направление и ведёт смену 09:00–18:00. Интенсивность = сколько задач агент берёт в день.</div>
  ${AGENTS.map(a=>{
    const c=S.cfg[a.key], open=S.openAgent===a.key;
    const pbs=PLAYBOOKS.filter(p=>p.agent===a.key);
    const active=pbs.filter(p=>c.playbooks.includes(p.id));
    return `<div class="panel" style="${open?`border-color:${a.accent}aa`:''};cursor:pointer" onclick="S.openAgent=${open?'null':`'${a.key}'`};render()">
      <div class="row"><div class="ava" style="background:${a.accent}22;font-size:19px">${a.emoji}</div>
        <div class="grow"><div style="font-weight:700;font-size:16px">${a.name}</div><div class="sub" style="color:${a.accent}">${a.dir}</div><div class="sub">${a.mission}</div></div>
        <div class="switch ${c.enabled?'on':''}" style="background:${c.enabled?a.accent:''}" onclick="event.stopPropagation();S.cfg['${a.key}'].enabled=!S.cfg['${a.key}'].enabled;render()"><i></i></div></div>
      <div class="sub" style="margin-top:9px">KPI: ${a.kpi}</div>
      <div class="chips" style="margin-top:10px">${['advise|Советник','prepare|Исполнитель','schedule|Планировщик'].map(o=>{const [v,l]=o.split('|');
        return `<button class="pill ${c.autonomy===v?'on':''}" style="${c.autonomy===v?`background:${a.accent}`:''}" onclick="event.stopPropagation();S.cfg['${a.key}'].autonomy='${v}';render()">${l}</button>`}).join('')}</div>
      <div class="sub" style="margin-top:7px">${{advise:'Только план и рекомендации. Ничего не готовит к публикации.',prepare:'Готовит пакеты и ждёт твоего одобрения.',schedule:'Сам ставит готовые пакеты в очередь по слотам. Публикация всё равно за тобой.'}[c.autonomy]}</div>
      <div class="row" style="margin-top:11px"><span class="sub">интенсивность</span>
        <div class="bar grow"><i style="width:${(c.intensity-1)/4*100}%;background:${a.accent}"></i></div>
        <b class="mono" style="color:${a.accent}">${c.intensity}</b>
        <input type="range" min="1" max="5" value="${c.intensity}" style="width:64px" onclick="event.stopPropagation()" oninput="S.cfg['${a.key}'].intensity=+this.value;render()">
      </div>
      <div class="sub" style="margin-top:6px">плейбуков: ${active.length}/${pbs.length} · задач в смене ≈ ${2+c.intensity}</div>
      ${open?`<div style="margin-top:10px;border-top:1px solid var(--line);padding-top:6px" onclick="event.stopPropagation()">
        ${pbs.map(p=>`<div class="playbook"><div class="check ${c.playbooks.includes(p.id)?'on':''}" style="${c.playbooks.includes(p.id)?`background:${a.accent}`:''}" onclick="togglePb('${a.key}','${p.id}')"></div>
          <div class="grow"><div style="font-size:13.5px;font-weight:600">${p.title}</div><div class="sub">${p.summary}</div>
          <div class="chips" style="margin-top:6px">${p.kinds.map(k=>`<span class="tag">${byId(k).title}</span>`).join('')}</div></div>
          <span class="sub" style="max-width:74px;text-align:right">${p.cadence}</span></div>`).join('')}
        <div class="sub" style="margin-top:8px">Открыть материалы агента → <b style="color:${a.accent}" onclick="S.tab='tasks';S.filter='${a.key}';render()">вкладка «Задачи»</b></div>
      </div>`:''}
    </div>`;
  }).join('')}
  <div class="panel soft" style="margin-top:4px"><div class="h" style="font-size:14.5px">Как читать оценку</div>
  <div class="sub" style="margin-top:5px">Оценка = сумма влияния закрытых задач (impact плейбука), а не «активность ради активности». 100/100 означает, что агент прогнал всё включённое. Это не прогноз роста: реальную цену видно по метрике, которую агент сам называет, через 7–14 дней.</div></div>`;
}
function togglePb(a,p){
  const list=S.cfg[a].playbooks;
  S.cfg[a].playbooks = list.includes(p)? list.filter(x=>x!==p) : [...list,p];
  render();
}

function viewTasks(){
  const f=S.filter;
  const list = f==='approval'?S.tasks.filter(t=>t.status==='approval')
    : f==='queue'?S.queue : f==='done'?S.tasks.filter(t=>t.status==='done'||t.status==='queued')
    : AGENTS.some(a=>a.key===f)? S.tasks.filter(t=>t.agent===f&&t.status!=='planned') : S.tasks;
  const filters=[['approval','Ждут одобрения',S.tasks.filter(t=>t.status==='approval').length],
    ['queue','Очередь',S.queue.filter(q=>q.state==='ready').length],
    ['done','Сделано',S.tasks.filter(t=>t.status==='done'||t.status==='queued').length],
    ...AGENTS.map(a=>[a.key,a.emoji+a.name,S.tasks.filter(t=>t.agent===a.key&&t.status!=='planned').length]),
    ['all','Все',S.tasks.length]];
  return `<div class="sec" style="margin-top:4px">Очередь и одобрение</div>
  <div class="sub" style="margin:-2px 2px 10px">Агент готовит материал, но публичное действие подтверждаешь ты. Не перестраховка: аккаунт твой, и бан за накрутку тоже твой.</div>
  <div class="chips" style="margin-bottom:12px">${filters.map(([k,l,n])=>`<button class="pill ${f===k?'on':''}" style="${f===k?'background:var(--violet)':''}" onclick="S.filter='${k}';render()">${l} <b>${n}</b></button>`).join('')}</div>
  ${!list.length?`<div class="panel"><div class="sub">${f==='approval'?'Ничего не ждёт одобрения — смена идёт чисто.':'Пусто. Запусти смену на вкладке «Смена», чтобы агенты начали готовить пакеты.'}</div></div>`:''}
  ${f==='queue'? S.queue.map(q=>{const kind=byId(q.kind);return `<div class="task">
      <div class="row"><div class="ava" style="width:30px;height:30px;font-size:15px;background:${agent(q.agent).accent}22">${agent(q.agent).emoji}</div>
      <div class="grow"><div style="font-weight:700;font-size:14px">${kind.title}</div><div class="sub">${q.agent==='scout'?'TikTok':'YouTube'} · слот ${clock(q.slot)} · ${q.state==='ready'?'готово к публикации':'опубликовано вручную'}</div></div></div>
      <div class="task out full">${kind.output.join('\n')}</div>
      ${q.state==='ready'?`<div class="row" style="margin-top:10px"><button class="btn ok" onclick="published('${q.id}')">Опубликовал</button><button class="btn ghost" onclick="S.queue=S.queue.filter(x=>x.id!=='${q.id}');render()">Убрать</button></div>
      <div class="sub" style="margin-top:8px">Скопируй текст в YouTube Studio / TikTok Studio — приложение не имеет прав на публикацию и не получит их.</div>`:''}
    </div>`}).join('')
  : list.map(t=>{const kind=byId(t.kind);const art=S.artifacts.find(a=>a.id===t.out);const riskC=kind.risk==='low'?'var(--ok)':kind.risk==='medium'?'var(--sun)':'var(--danger)';
    return `<div class="task">
      <div class="row"><span style="font-size:16px">${agent(t.agent).emoji}</span>
        <div class="grow"><div style="font-weight:700;font-size:14.5px">${kind.title}</div>
        <div class="sub">${agent(t.agent).name} · слот ${clock(t.slot)} · ~${kind.effort} мин</div></div>
        <span class="tag" style="color:${agent(t.agent).accent}">${t.status==='running'?'выполняется':t.status==='approval'?'ждёт одобрения':t.status==='queued'?'в очереди':t.status==='skipped'?'пропущено':'готово'}</span></div>
      <div class="sub" style="margin-top:7px">${kind.what}</div>
      <div class="chips" style="margin-top:8px"><span class="tag" style="color:${riskC}">риск: ${kind.risk==='low'?'низкий':kind.risk==='medium'?'средний':'высокий'}</span><span class="tag">метрика: ${kind.metric}</span><span class="tag">выход: ${kind.out}</span></div>
      ${t.status==='running'?`<div class="bar" style="margin-top:9px"><i style="width:${Math.round(t.progress*100)}%;background:${agent(t.agent).accent}"></i></div>`:''}
      ${art?`<div class="task out ${S.expanded[art.id]?'full':''}" onclick="S.expanded['${art.id}']=!S.expanded['${art.id}'];render()">${S.expanded[art.id]?art.body:art.body.slice(0,200)+(art.body.length>200?'…':'')}
        <div class="sub" style="margin-top:6px">${S.expanded[art.id]?'свернуть':'развернуть материал · офлайн-движок'}</div></div>`:''}
      ${t.status==='approval'?`<div class="row" style="margin-top:11px"><button class="btn ok" onclick="approve('${t.id}')">Одобрить → в очередь</button><button class="btn ghost" onclick="skip('${t.id}')">Пропустить</button></div>`:''}
    </div>`}).join('')}`;
}

function series(platform, metric){
  const days=60; const out=[];
  for(let i=0;i<days;i++){
    const d=new Date(Date.now()-(days-i)*864e5);
    const seed=Math.abs(Math.sin((d.getDate()+d.getMonth()*31+(platform==='yt'?1:7))*1.7));
    const ramp=1+i/55, wave=1+.14*Math.sin(i/3.1), we=d.getDay()===0||d.getDay()===6?1.18:1;
    const base=platform==='yt'?5200:13400, subs=platform==='yt'?18420:27150;
    const views=Math.round(base*wave*we*ramp), gained=Math.max(3,Math.round(views/(platform==='yt'?210:340))+Math.floor(seed*7));
    out.push({date:d.toISOString().slice(5,10),
      subs: subs + gained * i,
      views, ret:platform==='yt'?41+seed*4.5:58+seed*5.5,
      er:(views/34+views/300+views/720)/views*100, nw:platform==='yt'?38+seed*13:71+seed*5.7,
      ctr:platform==='yt'?4.2+seed*2.1:8.5+seed*3.1, comments:Math.round(views/300)});
  }
  const map={subs:r=>r.subs,views:r=>r.views,ret:r=>r.ret,er:r=>r.er,nw:r=>r.nw,ctr:r=>r.ctr};
  return out.map(o=>({...o,v:map[metric](o)}));
}
let PLAT='yt';
function viewGrowth(){
  const mets=[['subs','Подписчики'],['views','Просмотры'],['ret','Удержание'],['er','Вовлечённость'],['nw','Новая ауд.'],['ctr','CTR']];
  const cur = series(PLAT, GROW_METRIC);
  const first = Math.min(...cur.map(r=>r.v));
  const m2 = series(PLAT,'views').map(r=>r.v), l2 = m2[m2.length-1];
  const g=S.goals;
  const bars=[['Новые подписчики / нед',128,g.subs,'чел.','var(--violet)'],['Задач закрыто сегодня',S.tasks.filter(t=>t.status==='done').length,Math.max(1,S.tasks.length),'шт.','var(--mint)'],
    ['Удержание',series(PLAT,'ret').slice(-1)[0].v,g.retention,'%','var(--amber)'],['Вовлечённость',series(PLAT,'er').slice(-1)[0].v,g.er,'%','var(--sun)']];
  return `<div class="sec" style="margin-top:4px">Прирост аудитории</div>
  <div class="chips" style="margin-bottom:10px">${[['yt','YouTube'],['tt','TikTok']].map(([k,l])=>`<button class="pill ${PLAT===k?'on':''}" style="${PLAT===k?'background:var(--violet)':''}" onclick="PLAT='${k}';render()">${l}</button>`).join('')}</div>
  <div class="panel">
    <div class="chips">${mets.map(([k,l])=>`<button class="pill ${GROW_METRIC===k?'on':''}" style="${GROW_METRIC===k?'background:var(--mint);color:#04160f':''}" onclick="GROW_METRIC='${k}';render()">${l}</button>`).join('')}</div>
    <div style="height:12px"></div>
    ${(()=>{const v=series(PLAT,GROW_METRIC).map(r=>r.v),mn=Math.min(...v),mx=Math.max(...v);const p=v.map((x,i)=>`${(i/(v.length-1)*344+23).toFixed(1)},${(150-(x-mn)/((mx-mn)||1)*126).toFixed(1)}`).join(' ');
      return `<svg viewBox="0 0 390 160" style="width:100%;height:150px"><defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--mint)" stop-opacity=".35"/><stop offset="1" stop-color="var(--mint)" stop-opacity="0"/></linearGradient></defs>
      ${[1,2,3].map(i=>`<line x1="23" y1="${i*36+6}" x2="367" y2="${i*36+6}" stroke="#ffffff12"/>`).join('')}
      <polygon points="23,150 ${p} 367,150" fill="url(#g1)"/><polyline points="${p}" fill="none" stroke="var(--mint)" stroke-width="2.2" stroke-linejoin="round"/></svg>`})()}
    <div class="row sb" style="margin-top:6px"><span class="sub">${series(PLAT,GROW_METRIC)[0].date}</span><span class="sub">${series(PLAT,GROW_METRIC).slice(-1)[0].date}</span></div>
    <div class="row sb" style="margin-top:10px">
      <div><div class="stat">сейчас<b>${fmtV(series(PLAT,GROW_METRIC).slice(-1)[0].v)}</b></div></div>
      <div><div class="stat">за период<b style="color:${cur.slice(-1)[0].v>=first?'var(--ok)':'var(--danger)'}">${cur.slice(-1)[0].v>=first?'+':''}${fmtV(cur.slice(-1)[0].v - first)}</b></div></div>
      <div><div class="stat">просмотры<b>${fmtV(l2)}</b></div></div>
      <div><div class="stat">неделя к неделе<b style="color:var(--ok)">+${(((l2-m2[m2.length-8])/m2[m2.length-8])*100).toFixed(1)}%</b></div></div>
    </div>
  </div>
  <div class="sec">Цели Work Day</div>
  ${bars.map(([l,c,t,u,col])=>`<div class="panel" style="padding:11px 14px;margin-bottom:8px"><div class="row sb"><span style="font-size:13px">${l}</span><span class="sub mono">${fmtV(c)} / ${fmtV(t)} ${u}</span></div>
    <div class="bar" style="margin-top:7px"><i style="width:${Math.min(100,c/t*100)}%;background:${col}"></i></div></div>`).join('')}
  <div class="sec">Свои цифры вместо демо</div>
  <div class="panel"><div class="sub">YouTube Studio → Аналитика → «Скачать CSV» · TikTok Studio → Analytics → Export. Строка: <code style="font-size:11px">дата,площадка,просмотры,подписчики,удержание,лайки,комменты,репосты</code></div>
  <textarea class="field" id="csv" placeholder="2026-10-01,YouTube,5210,18420,44,153,17,4&#10;2026-10-01,TikTok,13400,27150,58,400,45,19"></textarea>
  <div class="row" style="margin-top:10px"><button class="btn" onclick="importCsv()">Импортировать</button><button class="btn ghost" onclick="toast('В Android-версии: YouTube Data API v3, только чтение статистики канала')">Подтянуть YouTube API</button></div></div>`;
}
let GROW_METRIC='subs';
function importCsv(){
  const txt=(document.getElementById('csv').value||'').trim();
  if(!txt){toast('Вставь строки CSV');return;}
  toast('В Android-версии это парсер AnalyticsImporter: строки уходят в график и в отчёты агентов');
}
function fmtV(v){return v>=1e6?(v/1e6).toFixed(2)+'M':v>=1000?(v/1000).toFixed(1)+'k':(Math.round(v*10)/10).toString()}

function viewSettings(){
  const L=S.llm;
  return `<div class="sec" style="margin-top:4px">Настройки</div>
  <div class="panel"><div class="row"><div class="grow"><div class="h">Модель для генерации</div>
    <div class="sub">${L.enabled&&L.key?'онлайн · '+L.model:'офлайн-движок (шаблоны, без сети)'}</div></div>
    <div class="switch ${L.enabled?'on':''}" onclick="S.llm.enabled=!S.llm.enabled;render()"><i></i></div></div>
    <label class="lbl">API-адрес (OpenAI-совместимый)</label><input class="field" value="${L.base}">
    <label class="lbl">Ключ</label><input class="field" placeholder="sk-…" value="${L.key}">
    <label class="lbl">Модель</label><input class="field" placeholder="gpt-4o-mini" value="${L.model}">
    <div class="row" style="margin-top:11px"><button class="btn" onclick="S.llm.enabled=true;toast('Ключ остаётся на устройстве, запрос идёт напрямую в API');render()">Сохранить</button>
    <button class="btn ghost" onclick="toast('Проба: агенты ответят через выбранную модель')">Проверить</button></div>
    <div class="sub" style="margin-top:9px">Можно оставить выключенным: агенты продолжат планировать смены и собирать материалы офлайн-движком — интерфейс и порядок работы те же.</div></div>

  <div class="sec">Канал</div>
  <div class="panel">
    <label class="lbl">ID канала YouTube</label><input class="field" value="${S.profile.youtube}">
    <label class="lbl">Ник в TikTok</label><input class="field" value="${S.profile.tiktok}">
    <label class="lbl">Ниша — от неё зависят все тексты агентов</label><input class="field" value="${S.profile.niche}">
    <label class="lbl">Кто зритель</label><input class="field" value="${S.profile.audience}">
    <label class="lbl">Тон автора</label><textarea class="field">${S.profile.tone}</textarea>
    <div class="row sb" style="margin-top:11px"><span class="sub">ритм: <b>${S.profile.cadence}</b> ролика в неделю</span>
      <input type="range" min="1" max="14" value="${S.profile.cadence}" oninput="S.profile.cadence=+this.value;render()">
    </div>
    <button class="btn" style="margin-top:11px" onclick="toast('Профиль сохранён — агенты перестроят план смены')">Сохранить канал</button></div>

  <div class="sec" style="color:var(--danger)">Границы, которые не настраиваются</div>
  <div class="panel" style="background:#170f14;border-color:#3a2431">
    ${NEVER.map(n=>`<div class="row" style="align-items:flex-start;padding:3px 0"><span style="color:var(--danger)">✕</span><span style="font-size:12.5px">${n}</span></div>`).join('')}
    <div class="sub" style="margin-top:9px">YouTube и TikTok банят за искусственную активность, и вместе с накруткой канал теряет органические охваты. Work Day поэтому усиливает то, что растёт по-настоящему: находимость, упаковку, ритм и отклик зрителей.</div>
  </div>
  <div class="panel soft"><div class="sub">Work Day 0.1.0 · 4 агента · ${PLAYBOOKS.length} плейбуков · ${ACTIONS.length} действий. Данные смены лежат в одном JSON на устройстве, своего сервера у приложения нет.</div></div>`;
}

window.togglePb=togglePb; window.approve=approve; window.skip=skip; window.published=published;
window.startShift=startShift; window.pauseShift=pauseShift; window.stopShift=stopShift;
window.importCsv=importCsv; window.PLAT_SET=()=>{};
render();


/*
 * Крючок для теста: preview/engine.test.js подставляет globalThis.__WORKDAY_TEST_HOOK__
 * и забирает себе чистые функции движка. В браузере хука нет — файл ведёт себя как обычный скрипт.
 */
if (typeof globalThis.__WORKDAY_TEST_HOOK__ === 'function') {
  globalThis.__WORKDAY_TEST_HOOK__({
    S, AGENTS, ACTIONS, PLAYBOOKS, NEVER,
    plan, tick, report, startShift, pauseShift, stopShift, approve, skip, published,
    togglePb, byId, clock, series, log,
    viewShift, viewAgents, viewTasks, viewGrowth, viewSettings,
    SHIFT_START, SHIFT_END,
    A, viewAuth, viewLock, viewAccount, linkStart, doSignIn, doRegister, doReset, tryUnlock,
  });
}

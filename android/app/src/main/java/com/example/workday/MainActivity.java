package com.example.workday;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/**
 * Work Day — ежедневник роста канала на YouTube и TikTok.
 *
 * Приложение помогает привлекать и удерживать аудиторию контентом:
 * крючками, коллаборациями, призывами к действию, регулярностью и
 * разбором собственных цифр.
 *
 * Здесь нет накрутки просмотров, авто-лайков, авто-подписок и обхода IP:
 * это запрещено правилами платформ и снижает органический охват канала.
 * Шаринг текста — обычный системный Intent, вы отправляете его сами.
 */
public class MainActivity extends Activity {

    private Db db;
    private String today;

    private Button[] tabs;
    private View[] panels;

    private Spinner attractPlatform, attractNiche, attractTone;
    private Spinner growPlatform, activityType, activityNiche, activityPlatform;
    private Spinner planPlatform, statPlatform;

    private EditText attractTopic, growSubs, growViews, activityTopic;
    private EditText planTopic, planDay, statName, statViews, statLikes, statComments, statShares;

    private TextView dayHeader, rulesText, attractOut, growSummary, activityOut, planSummary, statSummary;
    private LinearLayout routineList, growList, planList, statList;
    private Button attractCopy, attractShare, activityCopy, activityShare;

    private static final int BLUE = 0xFF2F6FEB;
    private static final int CARD = 0xFF171A21;
    private static final int TEXT = 0xFFE6E8EE;
    private static final int DIM = 0xFF9AA3B2;
    private static final int BUTTON = 0xFF252A34;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        db = new Db(this);
        today = Content.today();

        bind();
        setupTabs();
        setupSpinners();

        planDay.setText(today);
        rulesText.setText(Generator.growthRules());

        findViewById(R.id.attractBtn).setOnClickListener(v -> {
            String t = attractTopic.getText().toString();
            attractOut.setText(Generator.attract(t,
                    attractNiche.getSelectedItemPosition(),
                    attractPlatform.getSelectedItemPosition(),
                    attractTone.getSelectedItemPosition()));
            show(attractCopy, attractShare);
        });

        findViewById(R.id.attractCollabBtn).setOnClickListener(v -> {
            String t = attractTopic.getText().toString();
            attractOut.setText(Generator.collab(t, attractNiche.getSelectedItemPosition()));
            show(attractCopy, attractShare);
        });

        attractCopy.setOnClickListener(v -> copy(attractOut.getText().toString()));
        attractShare.setOnClickListener(v -> share(attractOut.getText().toString()));

        findViewById(R.id.activityBtn).setOnClickListener(v -> {
            String t = activityTopic.getText().toString();
            activityOut.setText(Generator.activity(
                    activityType.getSelectedItemPosition(), t,
                    activityNiche.getSelectedItemPosition(),
                    activityPlatform.getSelectedItemPosition()));
            show(activityCopy, activityShare);
        });

        activityCopy.setOnClickListener(v -> copy(activityOut.getText().toString()));
        activityShare.setOnClickListener(v -> share(activityOut.getText().toString()));

        findViewById(R.id.growAdd).setOnClickListener(v -> {
            int subs = num(growSubs);
            if (subs <= 0) {
                toast("Введите число подписчиков");
                return;
            }
            db.addSnap(today, Generator.PLATFORMS[growPlatform.getSelectedItemPosition()],
                    subs, num(growViews));
            growSubs.setText("");
            growViews.setText("");
            renderGrowth();
        });

        growPlatform.setOnItemSelectedListener(new SimpleSelect() {
            @Override
            public void onSelect(int pos) {
                renderGrowth();
            }
        });

        findViewById(R.id.planAdd).setOnClickListener(v -> {
            String t = planTopic.getText().toString().trim();
            if (t.isEmpty()) {
                toast("Введите тему");
                return;
            }
            db.addPlan(t, Generator.PLATFORMS[planPlatform.getSelectedItemPosition()],
                    planDay.getText().toString().trim());
            planTopic.setText("");
            renderPlans();
        });

        findViewById(R.id.statAdd).setOnClickListener(v -> {
            String n = statName.getText().toString().trim();
            if (n.isEmpty()) {
                toast("Введите название");
                return;
            }
            db.addStat(n, Generator.PLATFORMS[statPlatform.getSelectedItemPosition()],
                    num(statViews), num(statLikes), num(statComments), num(statShares), today);
            statName.setText("");
            statViews.setText("");
            statLikes.setText("");
            statComments.setText("");
            statShares.setText("");
            renderStats();
        });

        renderRoutine();
        renderGrowth();
        renderPlans();
        renderStats();
    }

    private void bind() {
        attractPlatform = findViewById(R.id.attractPlatform);
        attractNiche = findViewById(R.id.attractNiche);
        attractTone = findViewById(R.id.attractTone);
        growPlatform = findViewById(R.id.growPlatform);
        activityType = findViewById(R.id.activityType);
        activityNiche = findViewById(R.id.activityNiche);
        activityPlatform = findViewById(R.id.activityPlatform);
        planPlatform = findViewById(R.id.planPlatform);
        statPlatform = findViewById(R.id.statPlatform);

        attractTopic = findViewById(R.id.attractTopic);
        growSubs = findViewById(R.id.growSubs);
        growViews = findViewById(R.id.growViews);
        activityTopic = findViewById(R.id.activityTopic);
        planTopic = findViewById(R.id.planTopic);
        planDay = findViewById(R.id.planDay);
        statName = findViewById(R.id.statName);
        statViews = findViewById(R.id.statViews);
        statLikes = findViewById(R.id.statLikes);
        statComments = findViewById(R.id.statComments);
        statShares = findViewById(R.id.statShares);

        dayHeader = findViewById(R.id.dayHeader);
        rulesText = findViewById(R.id.rulesText);
        attractOut = findViewById(R.id.attractOut);
        growSummary = findViewById(R.id.growSummary);
        activityOut = findViewById(R.id.activityOut);
        planSummary = findViewById(R.id.planSummary);
        statSummary = findViewById(R.id.statSummary);

        routineList = findViewById(R.id.routineList);
        growList = findViewById(R.id.growList);
        planList = findViewById(R.id.planList);
        statList = findViewById(R.id.statList);

        attractCopy = findViewById(R.id.attractCopy);
        attractShare = findViewById(R.id.attractShare);
        activityCopy = findViewById(R.id.activityCopy);
        activityShare = findViewById(R.id.activityShare);
    }

    private void setupTabs() {
        tabs = new Button[]{
                findViewById(R.id.tabDay),
                findViewById(R.id.tabAttract),
                findViewById(R.id.tabGrow),
                findViewById(R.id.tabActivity),
                findViewById(R.id.tabPlan)
        };
        panels = new View[]{
                findViewById(R.id.panelDay),
                findViewById(R.id.panelAttract),
                findViewById(R.id.panelGrow),
                findViewById(R.id.panelActivity),
                findViewById(R.id.panelPlan)
        };
        for (int i = 0; i < tabs.length; i++) {
            final int idx = i;
            tabs[i].setOnClickListener(v -> showTab(idx));
        }
        showTab(0);
    }

    private void showTab(int idx) {
        for (int i = 0; i < panels.length; i++) {
            panels[i].setVisibility(i == idx ? View.VISIBLE : View.GONE);
            tabs[i].setBackgroundTintList(ColorStateList.valueOf(i == idx ? BLUE : CARD));
            tabs[i].setTextColor(i == idx ? 0xFFFFFFFF : TEXT);
        }
    }

    private void setupSpinners() {
        fill(attractPlatform, Generator.PLATFORMS);
        fill(attractNiche, Content.NICHE_NAMES);
        fill(attractTone, Generator.TONES);
        fill(growPlatform, Generator.PLATFORMS);
        fill(activityType, Content.ACTIVITY_TYPES);
        fill(activityNiche, Content.NICHE_NAMES);
        fill(activityPlatform, Generator.PLATFORMS);
        fill(planPlatform, Generator.PLATFORMS);
        fill(statPlatform, Generator.PLATFORMS);
    }

    private void fill(Spinner s, String[] items) {
        ArrayAdapter<String> a = new ArrayAdapter<>(this, R.layout.spinner_item, items);
        a.setDropDownViewResource(R.layout.spinner_item);
        s.setAdapter(a);
    }

    // ---------- День ----------

    private void renderRoutine() {
        routineList.removeAllViews();
        for (int i = 0; i < Content.ROUTINE.length; i++) {
            final int idx = i;
            CheckBox cb = new CheckBox(this);
            cb.setText(Content.ROUTINE[i]);
            cb.setTextColor(TEXT);
            cb.setTextSize(15);
            cb.setPadding(dp(12), dp(10), dp(12), dp(10));
            cb.setBackgroundColor(CARD);
            cb.setChecked(db.routineDone(today, idx));
            cb.setOnCheckedChangeListener((v, checked) -> {
                db.setRoutine(today, idx, checked);
                renderRoutine();
            });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.setMargins(0, dp(6), 0, 0);
            routineList.addView(cb, lp);
        }
        int done = db.dayProgress(today, Content.ROUTINE.length);
        int streak = db.streak(today, Content.ROUTINE.length);
        dayHeader.setText("Сегодня: " + done + " из " + Content.ROUTINE.length
                + (streak > 0 ? "\nСерия: " + streak + " " + daysWord(streak) + " подряд" : "")
                + "\n\nСерия важнее идеального дня. Закрыл хотя бы половину — день не потерян.");
    }

    private static String daysWord(int n) {
        if (n % 10 == 1 && n % 100 != 11) return "день";
        if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return "дня";
        return "дней";
    }

    // ---------- Рост ----------

    private void renderGrowth() {
        growList.removeAllViews();
        String platform = Generator.PLATFORMS[growPlatform.getSelectedItemPosition()];
        List<Db.Snap> all = db.snaps();
        List<Db.Snap> sub = new ArrayList<>();
        for (Db.Snap s : all) if (s.platform.equals(platform)) sub.add(s);

        if (sub.size() < 2) {
            growSummary.setText("Пока нет данных.\n\nСохраняйте снимок раз в неделю: "
                    + "сколько подписчиков и просмотров сейчас. Через две точки приложение "
                    + "покажет скорость роста и прогноз.");
        } else {
            Db.Snap last = sub.get(0);
            Db.Snap first = sub.get(sub.size() - 1);
            long days = daysBetween(first.day, last.day);
            if (days < 1) days = 1;
            int delta = last.subs - first.subs;
            double perDay = delta / (double) days;
            growSummary.setText(platform + ": " + first.subs + " → " + last.subs + " подписчиков\n"
                    + "Прирост: " + delta + " за " + days + " " + daysWord((int) days) + "\n"
                    + "Скорость: " + String.format(Locale.US, "%.1f", perDay) + " в день\n"
                    + "Прогноз при той же скорости: через 30 дней ≈ "
                    + Math.round(last.subs + perDay * 30)
                    + ", через 90 дней ≈ " + Math.round(last.subs + perDay * 90)
                    + "\n\nПрогноз линейный. На практике при регулярном постинге рост чаще "
                    + "ускоряется, а при паузах — падает до нуля.");
        }

        for (Db.Snap s : sub) {
            growList.addView(row(s.day + " · " + s.subs + " подписчиков · "
                    + s.views + " просмотров", v -> {
                db.delSnap(s.id);
                renderGrowth();
            }));
        }
    }

    // ---------- План ----------

    private void renderPlans() {
        planList.removeAllViews();
        List<Db.Plan> list = db.plans();
        int done = 0;
        for (Db.Plan p : list) if (p.done) done++;
        planSummary.setText("Запланировано: " + list.size() + " · готово: " + done);

        for (Db.Plan p : list) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(12), dp(10), dp(12), dp(10));
            row.setBackgroundColor(p.done ? 0xFF12241B : CARD);

            TextView t = new TextView(this);
            t.setText((p.done ? "✓ " : "") + p.topic + "\n" + p.platform + " · " + p.day);
            t.setTextColor(p.done ? DIM : TEXT);
            t.setTextSize(14);
            row.addView(t, new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

            row.addView(smallButton(p.done ? "↺" : "✓", v -> {
                db.setPlanDone(p.id, !p.done);
                renderPlans();
            }), new LinearLayout.LayoutParams(dp(52), dp(52)));

            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(52), dp(52));
            lp.setMarginStart(dp(6));
            row.addView(smallButton("✕", v -> {
                db.delPlan(p.id);
                renderPlans();
            }), lp);

            planList.addView(row, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            planList.addView(gap());
        }
    }

    // ---------- Цифры роликов ----------

    private void renderStats() {
        statList.removeAllViews();
        List<Db.Row> list = db.stats();
        if (list.isEmpty()) {
            statSummary.setText("Пока нет записей. Вносите цифры после каждого ролика — "
                    + "через пару недель станет видно, что именно работает.");
        } else {
            long views = 0;
            Db.Row best = null;
            double sum = 0;
            for (Db.Row r : list) {
                views += r.views;
                sum += r.engagementRate();
                if (best == null || r.engagementRate() > best.engagementRate()) best = r;
            }
            statSummary.setText("Роликов: " + list.size() + " · просмотров всего: " + views + "\n"
                    + "Средняя вовлечённость: "
                    + String.format(Locale.US, "%.1f", sum / list.size()) + "%\n"
                    + "Лучший: «" + best.name + "» — "
                    + String.format(Locale.US, "%.1f", best.engagementRate()) + "%\n\n"
                    + "Повторите лучший формат серией. Один удачный ролик — это сигнал, "
                    + "какую тему брать дальше, а не разовый успех.");
        }

        for (Db.Row r : list) {
            statList.addView(row(r.name + " · " + r.platform + "\n" + r.views + " просмотров · "
                    + r.likes + " лайков · " + r.comments + " комм. · " + r.shares
                    + " репостов\nвовлечённость "
                    + String.format(Locale.US, "%.1f", r.engagementRate()) + "% · " + r.day, v -> {
                db.delStat(r.id);
                renderStats();
            }));
        }
    }

    // ---------- мелкие помощники ----------

    private interface Action {
        void run();
    }

    private View row(String text, Action onDelete) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(12), dp(10), dp(12), dp(10));
        row.setBackgroundColor(CARD);

        TextView t = new TextView(this);
        t.setText(text);
        t.setTextColor(TEXT);
        t.setTextSize(14);
        row.addView(t, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        row.addView(smallButton("✕", v -> onDelete.run()),
                new LinearLayout.LayoutParams(dp(52), dp(52)));
        return row;
    }

    private Button smallButton(String text, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        b.setTextColor(TEXT);
        b.setBackgroundTintList(ColorStateList.valueOf(BUTTON));
        b.setOnClickListener(l);
        return b;
    }

    private View gap() {
        View v = new View(this);
        v.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(6)));
        return v;
    }

    private void show(View... views) {
        for (View v : views) v.setVisibility(View.VISIBLE);
    }

    private long daysBetween(String a, String b) {
        SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd", Locale.US);
        try {
            Date d1 = f.parse(a);
            Date d2 = f.parse(b);
            if (d1 == null || d2 == null) return 1;
            return Math.max(1, (d2.getTime() - d1.getTime()) / 86400000L);
        } catch (ParseException e) {
            return 1;
        }
    }

    private int num(EditText e) {
        String s = e.getText().toString().trim();
        if (s.isEmpty()) return 0;
        try {
            return Integer.parseInt(s);
        } catch (NumberFormatException ex) {
            return 0;
        }
    }

    private void copy(String text) {
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm == null) return;
        cm.setPrimaryClip(ClipData.newPlainText("text", text));
        toast("Скопировано");
    }

    private void share(String text) {
        if (TextUtils.isEmpty(text)) return;
        Intent i = new Intent(Intent.ACTION_SEND);
        i.setType("text/plain");
        i.putExtra(Intent.EXTRA_TEXT, text);
        startActivity(Intent.createChooser(i, "Отправить"));
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show();
    }

    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density + 0.5f);
    }

    private abstract static class SimpleSelect implements AdapterView.OnItemSelectedListener {
        @Override
        public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
            onSelect(position);
        }

        @Override
        public void onNothingSelected(AdapterView<?> parent) {
        }

        public abstract void onSelect(int pos);
    }
}

package com.example.creatorkit;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/**
 * Инструмент роста канала: идеи, описания, план публикаций, аналитика.
 *
 * Приложение НЕ накручивает просмотры и не автоматизирует действия на
 * платформах. «Поделиться» — это обычный системный шаринг текста,
 * который вы отправляете реальным людям туда, куда хотите сами.
 */
public class MainActivity extends Activity {

    private Db db;

    private Button[] tabs;
    private View[] panels;

    private Spinner nicheSpin, platformSpin, nicheSpin2, toneSpin, planPlatformSpin, statPlatformSpin;
    private EditText kwEdit, topicEdit, planTopicEdit, planDayEdit;
    private EditText statNameEdit, statViewsEdit, statLikesEdit, statCommentsEdit, statSharesEdit;
    private TextView ideasOut, postOut, cadenceText, planSummary, statSummary;
    private Button copyIdeasBtn, copyPostBtn, sharePostBtn;
    private LinearLayout planList, statList;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        db = new Db(this);

        bindViews();
        setupTabs();
        setupSpinners();

        planDayEdit.setText(new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date()));

        findViewById(R.id.genIdeasBtn).setOnClickListener(v -> {
            String text = Generator.ideas(nicheSpin.getSelectedItemPosition(),
                    kwEdit.getText().toString());
            ideasOut.setText(text);
            copyIdeasBtn.setVisibility(View.VISIBLE);
        });

        copyIdeasBtn.setOnClickListener(v -> copy(ideasOut.getText().toString()));

        findViewById(R.id.genPostBtn).setOnClickListener(v -> generatePost());

        copyPostBtn.setOnClickListener(v -> copy(postOut.getText().toString()));

        sharePostBtn.setOnClickListener(v -> {
            String text = postOut.getText().toString();
            if (TextUtils.isEmpty(text)) return;
            Intent i = new Intent(Intent.ACTION_SEND);
            i.setType("text/plain");
            i.putExtra(Intent.EXTRA_TEXT, text);
            startActivity(Intent.createChooser(i, "Отправить описание"));
        });

        findViewById(R.id.addPlanBtn).setOnClickListener(v -> {
            String topic = planTopicEdit.getText().toString().trim();
            if (topic.isEmpty()) {
                toast("Введите тему");
                return;
            }
            db.addPlan(topic, Generator.PLATFORMS[planPlatformSpin.getSelectedItemPosition()],
                    planDayEdit.getText().toString().trim());
            planTopicEdit.setText("");
            renderPlans();
        });

        findViewById(R.id.addStatBtn).setOnClickListener(v -> {
            String name = statNameEdit.getText().toString().trim();
            if (name.isEmpty()) {
                toast("Введите название");
                return;
            }
            db.addStat(name, Generator.PLATFORMS[statPlatformSpin.getSelectedItemPosition()],
                    num(statViewsEdit), num(statLikesEdit), num(statCommentsEdit), num(statSharesEdit),
                    new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date()));
            statNameEdit.setText("");
            statViewsEdit.setText("");
            statLikesEdit.setText("");
            statCommentsEdit.setText("");
            statSharesEdit.setText("");
            renderStats();
        });

        platformSpin.setOnItemSelectedListener(new SimpleSelect() {
            @Override
            public void onSelect(int pos) {
                cadenceText.setText(Generator.cadence(pos));
            }
        });

        cadenceText.setText(Generator.cadence(0));
        renderPlans();
        renderStats();
    }

    private void bindViews() {
        nicheSpin = findViewById(R.id.nicheSpin);
        platformSpin = findViewById(R.id.platformSpin);
        nicheSpin2 = findViewById(R.id.nicheSpin2);
        toneSpin = findViewById(R.id.toneSpin);
        planPlatformSpin = findViewById(R.id.planPlatformSpin);
        statPlatformSpin = findViewById(R.id.statPlatformSpin);

        kwEdit = findViewById(R.id.kwEdit);
        topicEdit = findViewById(R.id.topicEdit);
        planTopicEdit = findViewById(R.id.planTopicEdit);
        planDayEdit = findViewById(R.id.planDayEdit);
        statNameEdit = findViewById(R.id.statNameEdit);
        statViewsEdit = findViewById(R.id.statViewsEdit);
        statLikesEdit = findViewById(R.id.statLikesEdit);
        statCommentsEdit = findViewById(R.id.statCommentsEdit);
        statSharesEdit = findViewById(R.id.statSharesEdit);

        ideasOut = findViewById(R.id.ideasOut);
        postOut = findViewById(R.id.postOut);
        cadenceText = findViewById(R.id.cadenceText);
        planSummary = findViewById(R.id.planSummary);
        statSummary = findViewById(R.id.statSummary);

        copyIdeasBtn = findViewById(R.id.copyIdeasBtn);
        copyPostBtn = findViewById(R.id.copyPostBtn);
        sharePostBtn = findViewById(R.id.sharePostBtn);

        planList = findViewById(R.id.planList);
        statList = findViewById(R.id.statList);
    }

    private void setupTabs() {
        tabs = new Button[]{
                findViewById(R.id.tabIdeas),
                findViewById(R.id.tabPost),
                findViewById(R.id.tabPlan),
                findViewById(R.id.tabStats)
        };
        panels = new View[]{
                findViewById(R.id.panelIdeas),
                findViewById(R.id.panelPost),
                findViewById(R.id.panelPlan),
                findViewById(R.id.panelStats)
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
            tabs[i].setBackgroundTintList(android.content.res.ColorStateList.valueOf(
                    i == idx ? 0xFF2F6FEB : 0xFF171A21));
            tabs[i].setTextColor(i == idx ? 0xFFFFFFFF : 0xFFE6E8EE);
        }
    }

    private void setupSpinners() {
        fill(nicheSpin, Niches.NAMES);
        fill(nicheSpin2, Niches.NAMES);
        fill(platformSpin, Generator.PLATFORMS);
        fill(toneSpin, Generator.TONES);
        fill(planPlatformSpin, Generator.PLATFORMS);
        fill(statPlatformSpin, Generator.PLATFORMS);
    }

    private void fill(Spinner s, String[] items) {
        ArrayAdapter<String> a = new ArrayAdapter<>(this, R.layout.spinner_item, items);
        a.setDropDownViewResource(R.layout.spinner_item);
        s.setAdapter(a);
    }

    private void generatePost() {
        String topic = topicEdit.getText().toString();
        String text = Generator.caption(topic,
                nicheSpin2.getSelectedItemPosition(),
                platformSpin.getSelectedItemPosition(),
                toneSpin.getSelectedItemPosition());
        postOut.setText(text);
        copyPostBtn.setVisibility(View.VISIBLE);
        sharePostBtn.setVisibility(View.VISIBLE);
    }

    // ---------- план ----------

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
            row.setBackgroundColor(p.done ? 0xFF12241B : 0xFF171A21);

            TextView t = new TextView(this);
            t.setText((p.done ? "✓ " : "") + p.topic + "\n" + p.platform + " · " + p.day);
            t.setTextColor(p.done ? 0xFF9AA3B2 : 0xFFE6E8EE);
            t.setTextSize(14);
            row.addView(t, new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

            Button b = new Button(this);
            b.setText(p.done ? "↺" : "✓");
            b.setAllCaps(false);
            b.setTextColor(0xFFE6E8EE);
            b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xFF252A34));
            b.setOnClickListener(v -> {
                db.setPlanDone(p.id, !p.done);
                renderPlans();
            });
            row.addView(b, new LinearLayout.LayoutParams(dp(52), dp(52)));

            Button d = new Button(this);
            d.setText("✕");
            d.setAllCaps(false);
            d.setTextColor(0xFFE6E8EE);
            d.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xFF252A34));
            d.setOnClickListener(v -> {
                db.delPlan(p.id);
                renderPlans();
            });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(52), dp(52));
            lp.setMarginStart(dp(6));
            row.addView(d, lp);

            planList.addView(row, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

            View gap = new View(this);
            planList.addView(gap, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, dp(6)));
        }
    }

    // ---------- аналитика ----------

    private void renderStats() {
        statList.removeAllViews();
        List<Db.Row> list = db.stats();
        if (list.isEmpty()) {
            statSummary.setText("Пока нет записей. Вносите цифры после каждого ролика — "
                    + "через пару недель станет видно, что работает.");
        } else {
            long views = 0;
            Db.Row best = null;
            for (Db.Row r : list) {
                views += r.views;
                if (best == null || r.engagementRate() > best.engagementRate()) best = r;
            }
            double er = 0;
            for (Db.Row r : list) er += r.engagementRate();
            er /= list.size();
            statSummary.setText("Роликов: " + list.size()
                    + " · просмотров всего: " + views
                    + "\nСредняя вовлечённость: " + String.format(Locale.US, "%.1f", er) + "%"
                    + "\nЛучший по вовлечённости: «" + best.name + "» — "
                    + String.format(Locale.US, "%.1f", best.engagementRate()) + "%"
                    + "\n\nСмотрите не на просмотры, а на вовлечённость: именно она решает, "
                    + "будет ли алгоритм показывать следующий ролик.");
        }

        for (Db.Row r : list) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(12), dp(10), dp(12), dp(10));
            row.setBackgroundColor(0xFF171A21);

            TextView t = new TextView(this);
            t.setText(r.name + " · " + r.platform + "\n"
                    + r.views + " просмотров · " + r.likes + " лайков · "
                    + r.comments + " комм. · " + r.shares + " репостов\nвовлечённость "
                    + String.format(Locale.US, "%.1f", r.engagementRate()) + "% · " + r.day);
            t.setTextColor(0xFFE6E8EE);
            t.setTextSize(14);
            row.addView(t, new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

            Button d = new Button(this);
            d.setText("✕");
            d.setAllCaps(false);
            d.setTextColor(0xFFE6E8EE);
            d.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xFF252A34));
            d.setOnClickListener(v -> {
                db.delStat(r.id);
                renderStats();
            });
            row.addView(d, new LinearLayout.LayoutParams(dp(52), dp(52)));

            statList.addView(row, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

            View gap = new View(this);
            statList.addView(gap, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, dp(6)));
        }
    }

    // ---------- мелочи ----------

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

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show();
    }

    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density + 0.5f);
    }

    /** Пустая реализация, чтобы не тащить все методы OnItemSelectedListener. */
    private abstract static class SimpleSelect implements android.widget.AdapterView.OnItemSelectedListener {
        @Override
        public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
            onSelect(position);
        }

        @Override
        public void onNothingSelected(android.widget.AdapterView<?> parent) {
        }

        public abstract void onSelect(int pos);
    }
}

package com.example.farmmonitor;

import android.app.Activity;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.method.LinkMovementMethod;
import android.text.Html;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {

    private EditText serverEdit;
    private EditText nameEdit;
    private Switch autoSwitch;
    private TextView infoText;
    private TextView statusText;
    private SharedPreferences prefs;
    private String deviceId;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences("farm", MODE_PRIVATE);
        deviceId = Settings.Secure.getString(getContentResolver(), Settings.Secure.ANDROID_ID);
        if (deviceId == null) deviceId = "unknown";

        serverEdit = findViewById(R.id.serverEdit);
        nameEdit = findViewById(R.id.nameEdit);
        autoSwitch = findViewById(R.id.autoSwitch);
        infoText = findViewById(R.id.infoText);
        statusText = findViewById(R.id.statusText);
        Button refreshBtn = findViewById(R.id.refreshBtn);
        Button sendBtn = findViewById(R.id.sendBtn);

        TextView notice = findViewById(R.id.noticeText);
        notice.setText(Html.fromHtml(getString(R.string.notice), Html.FROM_HTML_MODE_LEGACY));
        notice.setMovementMethod(LinkMovementMethod.getInstance());

        serverEdit.setText(prefs.getString("server", ""));
        nameEdit.setText(prefs.getString("name", Build.MODEL));
        autoSwitch.setChecked(prefs.getBoolean("auto", false));

        refreshBtn.setOnClickListener(v -> refresh());
        sendBtn.setOnClickListener(v -> send());

        autoSwitch.setOnCheckedChangeListener((btn, on) -> {
            saveSettings();
            if (on) {
                Scheduler.enable(this);
                statusText.setText("Автоотчёт включён: каждые 15 минут");
            } else {
                Scheduler.disable(this);
                statusText.setText("Автоотчёт выключен");
            }
        });

        if (nameEdit.getText().toString().isEmpty()) nameEdit.setText(Build.MODEL);
        if (serverEdit.getText().toString().isEmpty()) {
            serverEdit.setHint("например http://192.168.1.10:8000");
        }
        refresh();
    }

    private void saveSettings() {
        prefs.edit()
                .putString("server", serverEdit.getText().toString().trim())
                .putString("name", nameEdit.getText().toString().trim())
                .putString("device_id", deviceId)
                .putBoolean("auto", autoSwitch.isChecked())
                .apply();
    }

    private void refresh() {
        statusText.setText("Определяю подключение…");
        new Thread(() -> {
            Net.Info info = Net.detect(getApplicationContext());
            runOnUiThread(() -> {
                String conn = humanConn(info.connType);
                StringBuilder sb = new StringBuilder();
                sb.append("Публичный IP: ").append(info.ip != null ? info.ip : "—").append('\n');
                sb.append("Подключение: ").append(conn).append('\n');
                sb.append("Провайдер: ").append(info.org != null ? info.org : "—").append('\n');
                sb.append("Страна: ").append(info.country != null ? info.country : "—").append('\n');
                sb.append("ID устройства: ").append(deviceId);
                if (info.error != null) sb.append("\n\n").append(info.error);
                infoText.setText(sb.toString());
                statusText.setText(info.error != null ? "Нет подключения к интернету" : "Готово");
            });
        }).start();
    }

    private void send() {
        saveSettings();
        final String server = serverEdit.getText().toString().trim();
        final String name = nameEdit.getText().toString().trim();
        if (server.isEmpty()) {
            Toast.makeText(this, "Укажите адрес панели", Toast.LENGTH_SHORT).show();
            return;
        }
        statusText.setText("Отправляю отчёт…");
        new Thread(() -> {
            Net.Info info = Net.detect(getApplicationContext());
            String err = Net.report(server, deviceId, name, info, prefs.getLong("bytes", 0L));
            final String msg;
            if (err == null) {
                prefs.edit().putLong("last_ok", System.currentTimeMillis()).apply();
                msg = "Отчёт отправлен. IP " + (info.ip != null ? info.ip : "—");
            } else {
                msg = "Ошибка: " + err;
            }
            runOnUiThread(() -> statusText.setText(msg));
        }).start();
    }

    private static String humanConn(String t) {
        if (t == null) return "—";
        switch (t) {
            case "cellular": return "мобильные данные";
            case "wifi": return "Wi-Fi";
            case "ethernet": return "Ethernet";
            case "offline": return "нет подключения";
            default: return t;
        }
    }
}

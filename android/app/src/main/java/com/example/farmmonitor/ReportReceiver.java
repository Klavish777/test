package com.example.farmmonitor;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

/** Фоновый отчёт по будильнику из {@link Scheduler}. */
public class ReportReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(final Context ctx, final Intent intent) {
        final SharedPreferences prefs = ctx.getSharedPreferences("farm", Context.MODE_PRIVATE);
        if (!prefs.getBoolean("auto", false)) return;

        final PendingResult result = goAsync();
        new Thread(() -> {
            try {
                Net.Info info = Net.detect(ctx.getApplicationContext());
                String err = Net.report(
                        prefs.getString("server", ""),
                        prefs.getString("device_id", ""),
                        prefs.getString("name", ""),
                        info,
                        prefs.getLong("bytes", 0L));
                if (err != null) android.util.Log.w("FarmMonitor", "Отчёт не отправлен: " + err);
                else android.util.Log.i("FarmMonitor", "Отчёт отправлен, ip=" + info.ip);
            } finally {
                result.finish();
            }
        }).start();
    }
}

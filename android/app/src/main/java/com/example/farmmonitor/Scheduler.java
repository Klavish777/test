package com.example.farmmonitor;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.SystemClock;

/** Периодический отчёт раз в 15 минут (Android может сдвигать интервал ради батареи). */
public final class Scheduler {

    public static final long INTERVAL_MS = 15 * 60 * 1000L;
    private static final int REQ = 4711;

    private Scheduler() {}

    private static PendingIntent pi(Context ctx) {
        Intent i = new Intent(ctx, ReportReceiver.class);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        flags |= PendingIntent.FLAG_IMMUTABLE;
        return PendingIntent.getBroadcast(ctx, REQ, i, flags);
    }

    public static void enable(Context ctx) {
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        if (am == null) return;
        am.setInexactRepeating(AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + 60_000L, INTERVAL_MS, pi(ctx));
    }

    public static void disable(Context ctx) {
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        if (am == null) return;
        am.cancel(pi(ctx));
    }
}

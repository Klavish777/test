package com.example.farmmonitor;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

/** Восстанавливает расписание после перезагрузки. */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context ctx, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
        SharedPreferences prefs = ctx.getSharedPreferences("farm", Context.MODE_PRIVATE);
        if (prefs.getBoolean("auto", false)) Scheduler.enable(ctx);
    }
}

package com.example.creatorkit;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import java.util.ArrayList;
import java.util.List;

/** План публикаций и аналитика, введённая вручную. */
public final class Db extends SQLiteOpenHelper {

    private static final String NAME = "creatorkit.db";
    private static final int VER = 1;

    public Db(Context c) {
        super(c, NAME, null, VER);
    }

    @Override
    public void onCreate(SQLiteDatabase d) {
        d.execSQL("CREATE TABLE plans (_id INTEGER PRIMARY KEY, topic TEXT, platform TEXT, day TEXT, done INTEGER)");
        d.execSQL("CREATE TABLE stats (_id INTEGER PRIMARY KEY, name TEXT, platform TEXT, "
                + "views INTEGER, likes INTEGER, comments INTEGER, shares INTEGER, day TEXT)");
    }

    @Override
    public void onUpgrade(SQLiteDatabase d, int a, int b) {
        d.execSQL("DROP TABLE IF EXISTS plans");
        d.execSQL("DROP TABLE IF EXISTS stats");
        onCreate(d);
    }

    // ---------- план ----------

    public static final class Plan {
        public long id;
        public String topic;
        public String platform;
        public String day;
        public boolean done;
    }

    public void addPlan(String topic, String platform, String day) {
        ContentValues v = new ContentValues();
        v.put("topic", topic);
        v.put("platform", platform);
        v.put("day", day);
        v.put("done", 0);
        getWritableDatabase().insert("plans", null, v);
    }

    public List<Plan> plans() {
        List<Plan> out = new ArrayList<>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT _id, topic, platform, day, done FROM plans ORDER BY done, day", null);
        while (c.moveToNext()) {
            Plan p = new Plan();
            p.id = c.getLong(0);
            p.topic = c.getString(1);
            p.platform = c.getString(2);
            p.day = c.getString(3);
            p.done = c.getInt(4) == 1;
            out.add(p);
        }
        c.close();
        return out;
    }

    public void setPlanDone(long id, boolean done) {
        ContentValues v = new ContentValues();
        v.put("done", done ? 1 : 0);
        getWritableDatabase().update("plans", v, "_id=?", new String[]{String.valueOf(id)});
    }

    public void delPlan(long id) {
        getWritableDatabase().delete("plans", "_id=?", new String[]{String.valueOf(id)});
    }

    // ---------- аналитика ----------

    public static final class Row {
        public long id;
        public String name;
        public String platform;
        public int views;
        public int likes;
        public int comments;
        public int shares;
        public String day;

        public double engagementRate() {
            if (views <= 0) return 0.0;
            return (likes + comments + shares) * 100.0 / views;
        }
    }

    public void addStat(String name, String platform, int views, int likes, int comments, int shares, String day) {
        ContentValues v = new ContentValues();
        v.put("name", name);
        v.put("platform", platform);
        v.put("views", views);
        v.put("likes", likes);
        v.put("comments", comments);
        v.put("shares", shares);
        v.put("day", day);
        getWritableDatabase().insert("stats", null, v);
    }

    public List<Row> stats() {
        List<Row> out = new ArrayList<>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT _id, name, platform, views, likes, comments, shares, day "
                        + "FROM stats ORDER BY _id DESC", null);
        while (c.moveToNext()) {
            Row r = new Row();
            r.id = c.getLong(0);
            r.name = c.getString(1);
            r.platform = c.getString(2);
            r.views = c.getInt(3);
            r.likes = c.getInt(4);
            r.comments = c.getInt(5);
            r.shares = c.getInt(6);
            r.day = c.getString(7);
            out.add(r);
        }
        c.close();
        return out;
    }

    public void delStat(long id) {
        getWritableDatabase().delete("stats", "_id=?", new String[]{String.valueOf(id)});
    }
}

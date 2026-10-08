package com.example.creatorkit;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Собирает идеи, описания и хэштеги. Ничего не автоматизирует на платформах. */
public final class Generator {

    public static final String[] PLATFORMS = {"TikTok", "YouTube Shorts", "Instagram Reels", "YouTube"};

    public static final String[] TONES = {"Дружелюбный", "Экспертный", "Дерзкий", "Юмористический"};

    private Generator() {}

    public static String ideas(int nicheIdx, String keyword) {
        String niche = Niches.NAMES[nicheIdx];
        String kw = keyword.trim();
        String subject = kw.isEmpty() ? niche.toLowerCase(Locale.ROOT) : kw;
        StringBuilder s = new StringBuilder();
        s.append("Идеи для ниши «").append(niche).append("»\n\n");
        int seed = Math.abs((niche + kw).hashCode());
        List<String> picked = new ArrayList<>();
        for (int i = 0; i < 6; i++) {
            String f = Niches.FORMATS[(seed + i * 7) % Niches.FORMATS.length];
            picked.add("• " + f + " — про " + subject);
        }
        for (String p : picked) s.append(p).append('\n');
        s.append("\nКрючки для первых 3 секунд:\n");
        for (int i = 0; i < 4; i++) {
            s.append("• ").append(Niches.HOOKS[(seed + i * 3) % Niches.HOOKS.length]).append('\n');
        }
        return s.toString();
    }

    public static String caption(String topic, int nicheIdx, int platIdx, int toneIdx) {
        String[] tags = Niches.TAGS[nicheIdx];
        StringBuilder sb = new StringBuilder();

        sb.append("Платформа: ").append(PLATFORMS[platIdx]).append('\n');
        sb.append("Тон: ").append(TONES[toneIdx]).append("\n\n");

        sb.append("Заголовок:\n").append(title(topic, toneIdx)).append("\n\n");

        sb.append("Описание:\n").append(body(topic, toneIdx, platIdx)).append("\n\n");

        sb.append("Хэштеги:\n");
        for (String t : tags) sb.append(t).append(' ');
        sb.append("#fyp #foryou\n\n");

        sb.append("Что сделать перед публикацией:\n")
                .append("1) Первые 3 секунды — крючок, без вступления и логотипа.\n")
                .append("2) Субтитры вшиты в видео: многие смотрят без звука.\n")
                .append("3) Один призыв к действию в конце, не два.\n")
                .append("4) Отвечай на первые комментарии в первый час — это поднимает охват.\n");
        return sb.toString();
    }

    private static String title(String topic, int toneIdx) {
        String t = topic.trim();
        if (t.isEmpty()) t = "мой новый ролик";
        switch (toneIdx) {
            case 1: return "Разбор: " + t + " — что работает, а что нет";
            case 2: return "Перестань делать это. " + t;
            case 3: return t + " (и почему у меня всё пошло не по плану)";
            default: return t + " — делюсь, как делаю это сам";
        }
    }

    private static String body(String topic, int toneIdx, int platIdx) {
        String t = topic.trim().isEmpty() ? "этой теме" : topic.trim();
        StringBuilder b = new StringBuilder();
        switch (toneIdx) {
            case 1:
                b.append("Коротко по фактам про ").append(t).append(".\n")
                        .append("Показал три вещи: что реально влияет на результат, что выглядит важно, "
                                + "но не работает, и как проверить это самому за пару минут.\n");
                break;
            case 2:
                b.append("Если ты всё ещё делаешь ").append(t).append(" по-старому — зря тратишь время.\n")
                        .append("Показал, как делаю я и почему обычный способ не выдерживает критики.\n");
                break;
            case 3:
                b.append("Решил разобраться с ").append(t).append(" и, как водится, всё пошло не так.\n")
                        .append("Что смешно — в итоге сработало самое простое решение.\n");
                break;
            default:
                b.append("Рассказываю про ").append(t).append(" без прикрас — как есть у меня.\n")
                        .append("Если что-то не так делаю, напиши в комментариях, разберём вместе.\n");
        }
        b.append("Сохрани, чтобы не искать потом.");
        return b.toString();
    }

    /** Сколько постов в неделю имеет смысл держать на старте. */
    public static String cadence(int platIdx) {
        switch (platIdx) {
            case 0: return "TikTok: 1–2 ролика в день на старте. Алгоритм быстрее находит нишу, "
                    + "когда видит много сигналов подряд.";
            case 1: return "YouTube Shorts: 3–5 в неделю. Важна регулярность, а не частота — "
                    + "пропуск недели отбрасывает назад.";
            case 2: return "Reels: 3–4 в неделю плюс сторис ежедневно — сторис удерживают ядро аудитории.";
            default: return "YouTube: 1–2 длинных видео в неделю. Здесь решает удержание, "
                    + "а не количество — одно сильное лучше четырёх слабых.";
        }
    }
}

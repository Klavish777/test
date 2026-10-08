package com.example.workday;

import java.util.Locale;

/** Собирает тексты: привлечение, активность, коллаборации, выводы по росту. */
public final class Generator {

    public static final String[] PLATFORMS = {"TikTok", "YouTube Shorts", "Instagram Reels", "YouTube"};

    public static final String[] TONES = {"Дружелюбный", "Экспертный", "Дерзкий", "Юмористический"};

    private Generator() {}

    /** Привлечение: крючки, заголовки, хэштеги, время, кросс-промо. */
    public static String attract(String topic, int nicheIdx, int platIdx, int toneIdx) {
        String t = topic.trim();
        String subject = t.isEmpty() ? Content.NICHE_NAMES[nicheIdx].toLowerCase(Locale.ROOT) : t;
        int seed = Math.abs((subject + platIdx + toneIdx).hashCode());
        StringBuilder s = new StringBuilder();

        s.append("Площадка: ").append(PLATFORMS[platIdx]).append('\n');
        s.append("Ниша: ").append(Content.NICHE_NAMES[nicheIdx]).append("\n\n");

        s.append("Крючки для первых 3 секунд:\n");
        for (int i = 0; i < 3; i++) {
            s.append(i + 1).append(") ").append(Content.pick(Content.HOOKS, seed, i)).append('\n');
        }

        s.append("\nЗаголовки:\n");
        for (int i = 0; i < 3; i++) {
            s.append(i + 1).append(") ").append(title(subject, toneIdx, seed + i)).append('\n');
        }

        s.append("\nХэштеги:\n");
        for (String tag : Content.NICHE_TAGS[nicheIdx]) s.append(tag).append(' ');
        s.append("#fyp #foryou\n");

        s.append("\nКогда публиковать:\n").append(Content.BEST_TIME[platIdx]).append("\n\n");

        s.append("Кросс-промо без накрутки:\n")
                .append("— Один и тот же материал — три формата: вертикаль, нарезка на 15 секунд, "
                        + "текстовый пост с той же мыслью.\n")
                .append("— Ссылку на ролик ставь в описание профиля, а не только в комментарии.\n")
                .append("— Скинь ролик в 2–3 тематических чата и сообщества, где вы реально "
                        + "общаетесь. Это и есть привлечение аудитории.\n")
                .append("— Ответь на комментарии в первый час: это поднимает охват больше, "
                        + "чем любая уловка.\n");

        return s.toString();
    }

    private static String title(String subject, int toneIdx, int seed) {
        switch (toneIdx) {
            case 1: return "Разбор: " + subject + " — что работает, а что нет";
            case 2: return "Перестань делать это: " + subject;
            case 3: return subject + " (и почему всё пошло не по плану)";
            default:
                switch (seed % 3) {
                    case 0: return "Как я делаю " + subject + " — показываю без прикрас";
                    case 1: return subject + ": три вещи, которые я понял слишком поздно";
                    default: return subject + " — коротко и по делу";
                }
        }
    }

    /** Стимулирование активности: призывы, ответы, опросы, закрепы. */
    public static String activity(int typeIdx, String topic, int nicheIdx, int platIdx) {
        String t = topic.trim();
        String subject = t.isEmpty() ? Content.NICHE_NAMES[nicheIdx].toLowerCase(Locale.ROOT) : t;
        int seed = Math.abs((subject + typeIdx).hashCode());
        StringBuilder s = new StringBuilder();

        switch (typeIdx) {
            case 0:
                s.append("Призывы к действию — выбери один, не больше:\n\n");
                for (int i = 0; i < 4; i++) {
                    s.append("— ").append(Content.pick(Content.CTAS, seed, i)).append('\n');
                }
                s.append("\nПод ").append(PLATFORMS[platIdx]).append(" лучше всего заходит призыв, "
                        + "который просит написать одно слово: он дешёвый по усилию, "
                        + "и комментариев приходит больше.\n");
                s.append("Призыв про ").append(subject).append(" звучит так: «Напиши, на каком ты "
                        + "этапе с ").append(subject).append(" — разберу в следующем ролике».");
                break;
            case 1:
                s.append("Шаблоны ответов на комментарии:\n\n");
                for (int i = 0; i < 4; i++) {
                    s.append("— ").append(Content.pick(Content.REPLIES, seed, i)).append("\n");
                }
                s.append("\nОтвечай в первый час после публикации и отвечай развёрнуто: "
                        + "ответ в два слова не держит ветку.\n");
                break;
            case 2:
                s.append("Опросы для аудитории:\n\n");
                for (int i = 0; i < 4; i++) {
                    s.append("— ").append(Content.pick(Content.POLLS, seed, i)).append('\n');
                }
                s.append("\nОпрос — самый дешёвый способ поднять активность: людям не нужно "
                        + "придумывать текст, достаточно выбрать.\n");
                break;
            default:
                s.append("Закреплённый комментарий:\n\n");
                for (int i = 0; i < 3; i++) {
                    s.append("— ").append(Content.pick(Content.PINS, seed, i)).append("\n");
                }
                s.append("\nЗакрепи его сразу после публикации: он задаёт, о чём пойдёт речь "
                        + "в комментариях.\n");
                break;
        }
        return s.toString();
    }

    /** Коллаборации — самый быстрый легальный источник новой аудитории. */
    public static String collab(String topic, int nicheIdx) {
        String t = topic.trim();
        String subject = t.isEmpty() ? Content.NICHE_NAMES[nicheIdx].toLowerCase(Locale.ROOT) : t;
        StringBuilder s = new StringBuilder();
        s.append("Тема: ").append(subject).append("\n\n");
        s.append("Кому писать:\n");
        s.append("— Авторам примерно твоего размера, ±30%. Крупным писать бессмысленно: "
                + "не ответят. Слишком мелким — не даст охвата.\n");
        s.append("— Тем, у кого та же аудитория, но не прямой конкурент: смежная ниша "
                + "работает лучше всего.\n\n");
        s.append("Шаблоны первого сообщения:\n\n");
        for (int i = 0; i < 3; i++) {
            s.append(i + 1).append(") ")
                    .append(Content.COLLAB[i].replace("{тема}", subject)
                            .replace("{моя тема}", subject))
                    .append("\n\n");
        }
        s.append("Правило: пиши 10 авторам, ответят двое-трое, сработает один. "
                + "Это нормальная конверсия, не провал.\n");
        return s.toString();
    }

    /** Идеи для контента. */
    public static String ideas(int nicheIdx, String keyword) {
        String niche = Content.NICHE_NAMES[nicheIdx];
        String kw = keyword.trim();
        String subject = kw.isEmpty() ? niche.toLowerCase(Locale.ROOT) : kw;
        int seed = Math.abs((niche + kw).hashCode());
        StringBuilder s = new StringBuilder();
        s.append("Идеи для «").append(niche).append("»\n\n");
        for (int i = 0; i < 6; i++) {
            s.append("• ").append(Content.pick(Content.FORMATS, seed, i))
                    .append(" — про ").append(subject).append('\n');
        }
        s.append("\nКрючки:\n");
        for (int i = 0; i < 4; i++) {
            s.append("• ").append(Content.pick(Content.HOOKS, seed, i)).append('\n');
        }
        return s.toString();
    }

    /** Описание под публикацию. */
    public static String caption(String topic, int nicheIdx, int platIdx, int toneIdx) {
        String t = topic.trim();
        String subject = t.isEmpty() ? Content.NICHE_NAMES[nicheIdx].toLowerCase(Locale.ROOT) : t;
        StringBuilder sb = new StringBuilder();
        sb.append("Заголовок:\n").append(title(subject, toneIdx, 1)).append("\n\n");
        sb.append("Описание:\n").append(body(subject, toneIdx)).append("\n\n");
        sb.append("Хэштеги:\n");
        for (String tag : Content.NICHE_TAGS[nicheIdx]) sb.append(tag).append(' ');
        sb.append("#fyp #foryou\n\n");
        sb.append("Чек-лист перед публикацией:\n")
                .append("1) Крючок в первые 3 секунды, без вступления и логотипа.\n")
                .append("2) Субтитры вшиты в видео — многие смотрят без звука.\n")
                .append("3) Один призыв к действию в конце, не два.\n")
                .append("4) Первый час — отвечай на комментарии.\n");
        return sb.toString();
    }

    private static String body(String subject, int toneIdx) {
        StringBuilder b = new StringBuilder();
        switch (toneIdx) {
            case 1:
                b.append("Коротко по фактам про ").append(subject).append(".\n")
                        .append("Что реально влияет на результат, что только выглядит важным, "
                                + "и как проверить это самому за пару минут.\n");
                break;
            case 2:
                b.append("Если ты всё ещё делаешь ").append(subject)
                        .append(" по-старому — зря тратишь время.\n")
                        .append("Показал, как делаю я и почему обычный способ не выдерживает критики.\n");
                break;
            case 3:
                b.append("Решил разобраться с ").append(subject)
                        .append(" и, как водится, всё пошло не так.\n")
                        .append("Сработало в итоге самое простое решение.\n");
                break;
            default:
                b.append("Рассказываю про ").append(subject).append(" без прикрас — как есть у меня.\n")
                        .append("Если что-то делаю не так, напиши в комментариях, разберём вместе.\n");
        }
        b.append("Сохрани, чтобы не искать потом.");
        return b.toString();
    }

    public static String growthRules() {
        return Content.GROWTH_RULES;
    }
}

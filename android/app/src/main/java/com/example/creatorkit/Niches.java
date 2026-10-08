package com.example.creatorkit;

/** Ниши и их рабочие углы подачи. Worldwide — без привязки к региону. */
public final class Niches {

    public static final String[] NAMES = {
            "Бизнес и деньги", "Красота", "Еда и рецепты", "Фитнес и здоровье",
            "Путешествия", "Образование", "Технологии и гаджеты", "Игры",
            "Мода и стиль", "Авто", "Дом и ремонт", "Юмор",
            "Музыка", "Рукоделие", "Другое"
    };

    /** Хэштеги под нишу — без региональной привязки, рабочие по всему миру. */
    public static final String[][] TAGS = {
            {"#money", "#business", "#finance", "#entrepreneur", "#sidehustle", "#moneytips"},
            {"#beauty", "#makeup", "#skincare", "#beautytips", "#glowup", "#beautyhacks"},
            {"#food", "#recipe", "#cooking", "#foodie", "#easyrecipe", "#homecooking"},
            {"#fitness", "#workout", "#gym", "#health", "#fitmotivation", "#homeworkout"},
            {"#travel", "#wanderlust", "#traveltips", "#budgettravel", "#explore", "#travelguide"},
            {"#education", "#learn", "#study", "#howto", "#knowledge", "#studyhacks"},
            {"#tech", "#gadgets", "#technology", "#review", "#techtok", "#gadgetreview"},
            {"#gaming", "#gamer", "#gameplay", "#gamingclips", "#videogames", "#gaminghighlights"},
            {"#fashion", "#style", "#outfit", "#ootd", "#fashiontips", "#styletips"},
            {"#cars", "#auto", "#carreview", "#cartok", "#automotive", "#carlife"},
            {"#diy", "#home", "#renovation", "#interior", "#homedecor", "#diyproject"},
            {"#funny", "#comedy", "#humor", "#funnymoments", "#lol", "#relatable"},
            {"#music", "#musician", "#newmusic", "#songwriter", "#musictips", "#cover"},
            {"#handmade", "#craft", "#diycraft", "#handmadewithlove", "#crafttok", "#maker"},
            {"#viral", "#foryou", "#trending", "#tips", "#howto", "#creator"}
    };

    /** Рабочие форматы — пересекаются с любой нишей. */
    public static final String[] FORMATS = {
            "Разбор типичной ошибки",
            "До / после",
            "Топ-3 вещи, которые я делал неправильно",
            "Ответ на вопрос из комментариев",
            "Закулисье: как это делается на самом деле",
            "Один совет, который сработал за 30 секунд",
            "Миф против факта",
            "Что я купил и стоило ли оно того",
            "Начинающим: с чего я бы начал заново",
            "Сравнение: дёшево против дорого",
            "История провала и что я из неё вынес",
            "Проверка популярного совета на себе"
    };

    /** Крючки первых 3 секунд — от них зависит удержание. */
    public static final String[] HOOKS = {
            "Остановись, если делаешь это каждый день.",
            "Я потратил на это слишком много времени, чтобы молчать.",
            "Большинство делает это неправильно — сейчас покажу как надо.",
            "Это бесплатно, и почти никто об этом не знает.",
            "Ты теряешь деньги вот здесь — смотри.",
            "Три секунды внимания, и ты поймёшь, почему не получается.",
            "Я проверил это сам, результат удивил.",
            "Если бы я знал это раньше, сэкономил бы год.",
            "Смотри до конца — ошибка в конце самая частая.",
            "Не покупай это, пока не посмотришь."
    };

    private Niches() {}
}

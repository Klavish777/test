# Формат пакета BoardView

Приложение читает собственный открытый формат JSON — `smartphone-repair-os-board` v1.
Он специально простой, чтобы мастер мог подготовить данные вручную или скриптом.

## Общая структура

```json
{
  "format": "smartphone-repair-os-board",
  "version": 1,
  "board": {
    "name": "Плата Galaxy A52",
    "board_code": "SM-A525F_MB",
    "revision": "rev1",
    "dimensions": { "width": 62.0, "length": 128.0, "thickness": 1.0 },
    "source": "Собственные измерения / сервис-мануал (права: …)",
    "license_note": "Использование согласовано с правообладателем",
    "notes": "Произвольный комментарий",
    "photo_top": "top.jpg",
    "photo_bottom": "bottom.jpg"
  },
  "components": [
    {
      "designator": "U1201",
      "side": "top",
      "layer": "power",
      "type": "IC",
      "marking": "PM8150",
      "purpose": "PMIC",
      "package": "BGA",
      "rotation": 0,
      "position": { "x": 10.0, "y": 20.0, "z": 0.6 },
      "size": { "x": 3.0, "y": 3.0, "z": 1.0 },
      "marker": { "u": 0.42, "v": 0.55 },
      "notes": "Проверять при отсутствии питания"
    }
  ],
  "annotations": [
    { "label": "Нет питания", "body": "Проверить U1201", "component": "U1201", "color": "#3d8bfd" }
  ]
}
```

## Поля платы (`board`)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `name` | string | да | название платы в интерфейсе |
| `board_code` | string | нет | внутренний код платы |
| `revision` | string | нет | ревизия |
| `dimensions.width/length/thickness` | число (мм) | рекомендуется | без размеров 3D-сцена использует условный масштаб |
| `photo_top` / `photo_bottom` | имя файла | нет | относительно JSON-файла или корня ZIP |
| `source`, `license_note`, `notes` | string | нет | происхождение и права |

## Компоненты

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `designator` | string | да | позиционное обозначение: `U1201`, `C4502`, `R3201` |
| `side` | `top` / `bottom` | да (по умолчанию `top`) | сторона платы |
| `layer` | string | нет | слой для скрытия/показа (питание, RF, USB…) |
| `type` | string | нет | IC, конденсатор, резистор, разъём… |
| `marking` | string | нет | маркировка на корпусе (только достоверная) |
| `purpose` | string | нет | назначение (только достоверное) |
| `position.x/y/z` | число (мм) | для 3D | центр корпуса |
| `size.x/y/z` | число (мм) | для 3D | габариты корпуса |
| `rotation` | число (градусы) | нет | поворот вокруг оси Z |
| `marker.u/v` | число 0…1 | для фото | относительные координаты метки на фото |
| `notes` | string | нет | комментарий мастера |

**Координаты:** миллиметры, начало в левом нижнем углу платы, ось X — ширина,
ось Y — длина, ось Z — толщина. Компоненты верхней стороны имеют `z > 0`,
нижней — `z < 0`.

**Если геометрии нет** (`position`/`size` отсутствуют), компонент не рисуется
объёмным телом. Он остаётся в списке и карточке, а на фото показывается метка
(если задан `marker`).

## Метки (`annotations`)

`label` — короткая подпись, `body` — текст, `component` — обозначение компонента
(необязательно), `color` — цвет в hex.

## Импорт ZIP

ZIP-архив с одним JSON-пакетом и изображениями:

```
board.json
top.jpg
bottom.jpg
```

Распаковка безопасна: абсолютные пути, `..`, символические ссылки и zip-бомбы
отклоняются (см. `repair_os/core/security.py`).

## Ограничения формата

* Максимум 20 000 компонентов в пакете.
* Координаты и размеры — только числовые значения; приложение не «додумывает»
  недостающие размеры.
* Один пакет = одна плата. Для нескольких ревизий создайте несколько пакетов и
  привяжите их к одному устройству.

## Конвертация внешних форматов

Прямое чтение `.brd`, `.bdv`, `.pcb` (OpenBoardView/BoardViewer) не реализовано:
это бинарные форматы с неофициальной спецификацией. Рекомендуемый путь:

1. экспортируйте из вашего инструмента список компонентов (обозначение, сторона,
   координаты, поворот, тип) в CSV;
2. переведите миллиметры/милы в миллиметры (1 mil = 0.0254 мм);
3. соберите JSON-пакет скриптом:

```python
import csv, json

components = []
with open("components.csv", newline="", encoding="utf-8-sig") as handle:
    for row in csv.DictReader(handle):
        components.append({
            "designator": row["designator"].upper(),
            "side": row.get("side", "top").lower(),
            "type": row.get("type") or None,
            "position": {
                "x": float(row["x_mm"]),
                "y": float(row["y_mm"]),
                "z": float(row.get("z_mm") or 1.0),
            },
            "size": {
                "x": float(row.get("w_mm") or 1.0),
                "y": float(row.get("h_mm") or 0.5),
                "z": float(row.get("t_mm") or 0.4),
            },
        })

package = {
    "format": "smartphone-repair-os-board",
    "version": 1,
    "board": {"name": "Моя плата", "dimensions": {"width": 62, "length": 128, "thickness": 1}},
    "components": components,
    "annotations": [],
}
json.dump(package, open("board.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
```

4. импортируйте `board.json` через **3D BoardView → Импорт платы**.

Собственные конвертеры можно добавлять в `repair_os/services/board_packages.py`, не
меняя формат хранения в базе.

## Авторские права

Пакеты плат, схемы и фотографии — объекты авторского права. Загружайте только данные,
на которые у вас есть разрешение. Поле `license_note` отображается в карточке платы.
Демонстрационная плата в приложении синтетическая и помечена `ДЕМО`.

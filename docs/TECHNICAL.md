# Техническая документация

## Архитектура патчера

### Обзор

Linux NVIDIA Patcher состоит из нескольких ключевых компонентов:

1. **Patcher Core** (`src/patcher.py`) - основной модуль
2. **Driver Detector** (`src/driver_detector.py`) - обнаружение драйверов
3. **Backup Manager** (`src/backup_manager.py`) - управление резервными копиями
4. **Patch Files** (`patches/`) - бинарные патчи
5. **Utilities** (`tools/`) - вспомогательные утилиты

## Процесс патчинга

### 1. Обнаружение драйверов

```python
# Методы обнаружения в приоритетном порядке:
1. nvidia-smi --query-gpu=driver_version
2. modinfo nvidia
3. Поиск библиотек libnvidia-ml.so.*
4. Пакетные менеджеры (apt, rpm, yum)
```

### 2. Анализ модулей

```python
# Проверяемые параметры:
- Физическое существование файла
- ELF сигнатура (0x7F 'ELF')
- Размер файла
- Архитектура (x86_64)
- Контрольная сумма SHA256
```

### 3. Применение патча

```python
# Процесс применения:
1. Создание резервной копии
2. Проверка совместимости версии
3. Бинарное патчирование через утилиту patch
4. Вставка magic bytes для идентификации
5. Валидация результата
```

## Структура патчей

### Формат патча

```
nvidia_535.patch:
- Метаданные патча
- Оффсеты для модификации
- Оригинальные байты
- Патченые байты
- Magic bytes для идентификации
```

### Оффсеты для 535.274.02

```c
struct patch_offsets {
    unsigned long sig_check_offset;      // 0x00123456
    unsigned long dse_bypass_offset;     // 0x00123ABC  
    unsigned long verification_offset;   // 0x00123DEF
};
```

## Безопасность

### Проверки целостности

1. **До патчинга:**
   - SHA256 контрольные суммы
   - ELF валидация
   - Проверка размеров файлов

2. **После патчинга:**
   - Верификация magic bytes
   - Проверка примененных изменений
   - Тестовая загрузка модуля

### Изоляция процессов

- Все операции выполняются с правами root
- Временные файлы создаются в /tmp
- Бэкапы хранятся в /var/lib/nvidia-patcher/backups/

## Совместимость

### Поддерживаемые дистрибутивы

- Ubuntu 18.04+ 
- Debian 10+
- CentOS 7+/RHEL 7+
- Fedora 30+
- Arch Linux

### Требования к ядру

- Linux kernel 4.15+
- Поддержка модулей ядра
- Система защиты подписи модулей (может быть отключена)

## Отладка

### Уровни логирования

```python
logging.basicConfig(
    level=logging.INFO,  # DEBUG для детальной отладки
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/nvidia-patcher.log'),
        logging.StreamHandler()
    ]
)
```

### Полезные команды

```bash
# Проверка загруженных модулей
lsmod | grep nvidia

# Проверка версии драйвера
nvidia-smi --query-gpu=driver_version --format=csv,noheader

# Анализ ELF файла
readelf -h /path/to/nvidia.ko

# Поиск патчей
hexdump -C /path/to/nvidia.ko | grep -i "nvpt"
```

## Расширение функциональности

### Добавление новой версии драйвера

1. Создать файл патча: `patches/nvidia_XXX.patch`
2. Добавить версию в `supported_versions`
3. Обновить `patch_signatures` в `verify_patch.py`
4. Протестировать на чистой системе

### Добавление нового метода обнаружения

```python
def _get_custom_detection_method(self) -> Optional[Dict]:
    """Пользовательский метод обнаружения"""
    try:
        # Ваш код обнаружения
        return driver_info
    except Exception as e:
        self.logger.debug(f"Custom detection failed: {e}")
        return None
```

## Производительность

### Оптимизации

- Кэширование результатов обнаружения
- Параллельная обработка модулей
- Инкрементальные бэкапы

### Ресурсы

- Память: < 50MB во время работы
- Диск: ~100MB для бэкапов
- CPU: < 5% на современных системах

## Тестирование

### Unit тесты

```bash
# Запуск тестов
python3 -m pytest tests/

# Покрытие кода
python3 -m pytest --cov=src tests/
```

### Интеграционные тесты

```bash
# Тестирование на clean системе
sudo ./tests/integration_test.sh

# Тестирование отката
sudo ./tests/rollback_test.sh
```

## Устранение неисправностей

### Распространенные проблемы

1. **Permission denied**
   - Решение: sudo chmod +x scripts

2. **Module not found**
   - Решение: python3 -m pip install missing_module

3. **Patch failed**
   - Решение: проверьте версию драйвера

### Диагностика

```bash
# Проверка системного состояния
sudo dmesg | grep -i nvidia
sudo journalctl -u nvidia-patcher

# Проверка файлов
find /lib/modules -name "nvidia*.ko" 2>/dev/null
stat /usr/lib/x86_64-linux-gnu/nvidia-*/nvidia.ko
```

## Будущие улучшения

### Планируемые функции

- GUI интерфейс
- Автоматические обновления патчей
- Поддержка更多 GPU вендоров
- Облачная база данных совместимости

### Архитектурные изменения

- Переход на модульную архитектуру
- Поддержка плагинов
- Улучшенная обработка ошибок
- Метрики и мониторинг
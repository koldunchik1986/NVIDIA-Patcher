#!/bin/bash
#
# Утилита для извлечения и подготовки драйвера NVIDIA к патчингу
#

set -e

# Конфигурация
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EXTRACT_DIR="/tmp/nvidia-driver-extract"
LOG_FILE="/var/log/nvidia-extract.log"

# Логирование
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    echo "ERROR: $1" | tee -a "$LOG_FILE"
    exit 1
}

# Проверка зависимостей
check_dependencies() {
    log "Проверка зависимостей..."
    
    local deps=("bash" "tar" "find" "chmod" "chown")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            error "Зависимость не найдена: $dep"
        fi
    done
    
    # Проверка прав суперпользователя
    if [[ $EUID -ne 0 ]]; then
        error "Этот скрипт требует прав суперпользователя"
    fi
}

# Очистка временных файлов
cleanup() {
    if [[ -d "$EXTRACT_DIR" ]]; then
        log "Очистка временной директории: $EXTRACT_DIR"
        rm -rf "$EXTRACT_DIR"
    fi
}

# Установка обработчика очистки
trap cleanup EXIT

# Извлечение драйвера
extract_driver() {
    local driver_file="$1"
    
    if [[ ! -f "$driver_file" ]]; then
        error "Файл драйвера не найден: $driver_file"
    fi
    
    log "Извлечение драйвера из: $driver_file"
    
    # Создание временной директории
    mkdir -p "$EXTRACT_DIR"
    
    # Извлечение .run файла
    log "Распаковка .run файла..."
    
    # Проверяем, является ли файл .run архивом
    if file "$driver_file" | grep -q "shell script"; then
        # Это shell script архив
        log "Обнаружен shell script архив, извлечение..."
        
        # Создание директории для extracted файлов
        local extracted_dir="$EXTRACT_DIR/extracted"
        mkdir -p "$extracted_dir"
        
        # Запуск installer с параметром --extract-only
        cd "$EXTRACT_DIR"
        bash "$driver_file" --extract-only
        
        if [[ $? -eq 0 ]]; then
            log "Драйвер успешно извлечен"
        else
            error "Ошибка извлечения драйвера"
        fi
    else
        error "Неподдерживаемый формат файла драйвера"
    fi
}

# Поиск модулей ядра
find_kernel_modules() {
    log "Поиск модулей ядра..."
    
    local module_dir=""
    
    # Поиск директории с модулями
    for dir in "$EXTRACT_DIR"/*; do
        if [[ -d "$dir" && -f "$dir/kernel/nvidia.ko" ]]; then
            module_dir="$dir/kernel"
            break
        elif [[ -d "$dir" && -f "$dir/nvidia.ko" ]]; then
            module_dir="$dir"
            break
        fi
    done
    
    if [[ -z "$module_dir" ]]; then
        error "Модули ядра не найдены в извлеченном драйвере"
    fi
    
    log "Модули найдены в: $module_dir"
    
    # Копирование модулей в рабочую директорию
    local output_dir="$PROJECT_DIR/modules"
    mkdir -p "$output_dir"
    
    cp -r "$module_dir"/* "$output_dir/"
    
    log "Модули скопированы в: $output_dir"
    
    # Установка прав доступа
    chmod 644 "$output_dir"/*.ko
    chown root:root "$output_dir"/*.ko
    
    log "Права доступа установлены"
}

# Анализ драйвера
analyze_driver() {
    log "Анализ извлеченного драйвера..."
    
    local module_dir="$PROJECT_DIR/modules"
    
    # Проверка файлов модулей
    local modules=("nvidia.ko" "nvidia-drm.ko" "nvidia-modeset.ko" "nvidia-uvm.ko")
    
    for module in "${modules[@]}"; do
        if [[ -f "$module_dir/$module" ]]; then
            local size=$(stat -c%s "$module_dir/$module")
            local hash=$(sha256sum "$module_dir/$module" | cut -d' ' -f1)
            
            log "Модуль: $module"
            log "  Размер: $size байт"
            log "  SHA256: $hash"
            log ""
        else
            log "Модуль не найден: $module"
        fi
    done
    
    # Проверка сигнатуры ELF
    for module in "$module_dir"/*.ko; do
        if [[ -f "$module" ]]; then
            local magic=$(hexdump -C "$module" | head -1 | cut -d' ' -f2-5)
            log "$(basename "$module"): $magic"
        fi
    done
}

# Подготовка к патчингу
prepare_for_patching() {
    log "Подготовка к патчингу..."
    
    local module_dir="$PROJECT_DIR/modules"
    
    # Создание бэкапа оригинальных модулей
    local backup_dir="$PROJECT_DIR/backups/original"
    mkdir -p "$backup_dir"
    
    cp "$module_dir"/*.ko "$backup_dir/" 2>/dev/null || true
    
    log "Оригинальные модули сохранены в: $backup_dir"
    
    # Создание файла информации о драйвере
    local info_file="$PROJECT_DIR/driver_info.json"
    
    cat > "$info_file" << EOF
{
    "extracted_at": "$(date -Iseconds)",
    "driver_file": "$(basename "$1")",
    "modules": [
EOF
    
    local first=true
    for module in "$module_dir"/*.ko; do
        if [[ -f "$module" ]]; then
            if [[ "$first" == "true" ]]; then
                first=false
            else
                echo "," >> "$info_file"
            fi
            
            local module_name=$(basename "$module")
            local size=$(stat -c%s "$module")
            
            cat >> "$info_file" << EOF
        {
            "name": "$module_name",
            "path": "$module",
            "size": $size,
            "backup_path": "$backup_dir/$module_name"
        }
EOF
        fi
    done
    
    cat >> "$info_file" << EOF
    ]
}
EOF
    
    log "Информация о драйвере сохранена в: $info_file"
}

# Функция помощи
show_help() {
    cat << EOF
Использование: $0 [опции] <файл_драйвера>

Опции:
  -h, --help     Показать эту справку
  -v, --verbose  Подробный вывод
  -o, --output   Директория для извлеченных файлов (по умолчанию: $PROJECT_DIR/modules)

Аргументы:
  файл_драйвера  Путь к .run файлу драйвера NVIDIA

Примеры:
  $0 NVIDIA-Linux-x86_64-535.274.02.run
  $0 -v /path/to/NVIDIA-Linux-x86_64-535.274.02.run
  $0 -o /tmp/extracted NVIDIA-Linux-x86_64-535.274.02.run
EOF
}

# Основная функция
main() {
    local driver_file=""
    local output_dir="$PROJECT_DIR/modules"
    local verbose=false
    
    # Парсинг аргументов
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            -o|--output)
                output_dir="$2"
                shift 2
                ;;
            -*)
                error "Неизвестная опция: $1"
                ;;
            *)
                if [[ -z "$driver_file" ]]; then
                    driver_file="$1"
                else
                    error "Лишний аргумент: $1"
                fi
                shift
                ;;
        esac
    done
    
    # Проверка обязательных аргументов
    if [[ -z "$driver_file" ]]; then
        error "Не указан файл драйвера. Используйте -h для справки."
    fi
    
    # Настройка логирования
    if [[ "$verbose" == "true" ]]; then
        set -x
    fi
    
    log "Начало извлечения драйвера NVIDIA"
    log "Файл драйвера: $driver_file"
    log "Директория вывода: $output_dir"
    
    # Основные шаги
    check_dependencies
    extract_driver "$driver_file"
    find_kernel_modules
    analyze_driver
    prepare_for_patching "$driver_file"
    
    log "Извлечение драйвера завершено успешно!"
    log "Извлеченные модули находятся в: $output_dir"
    log "Для патчинга используйте: python3 $PROJECT_DIR/src/patcher.py --patch"
}

# Запуск
main "$@"
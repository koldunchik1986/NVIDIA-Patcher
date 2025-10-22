#!/bin/bash
#
# Инсталляционный скрипт для Linux NVIDIA Patcher
#

set -e

# Конфигурация
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="linux-nvidia-patcher"
INSTALL_DIR="/opt/$PROJECT_NAME"
BIN_DIR="/usr/local/bin"
SYSTEMD_DIR="/etc/systemd/system"
LOG_DIR="/var/log"
LIB_DIR="/var/lib/$PROJECT_NAME"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Логирование
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Проверка зависимостей
check_dependencies() {
    log "Проверка зависимостей..."
    
    local deps=("python3" "bash" "patch" "grep" "awk" "find")
    local missing_deps=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            missing_deps+=("$dep")
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        error "Отсутствуют зависимости: ${missing_deps[*]}"
    fi
    
    # Проверка Python модулей
    python3 -c "import sys, os" 2>/dev/null || error "Python 3 не имеет необходимых модулей"
    
    log "Все зависимости найдены"
}

# Проверка прав суперпользователя
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "Этот скрипт требует прав суперпользователя. Запустите с sudo."
    fi
}

# Проверка системы
check_system() {
    log "Проверка системы..."
    
    # Архитектура
    local arch=$(uname -m)
    if [[ "$arch" != "x86_64" ]]; then
        error "Поддерживается только архитектура x86_64"
    fi
    
    # ОС
    if [[ ! -f /etc/os-release ]]; then
        warn "Не удалось определить дистрибутив Linux"
    else
        source /etc/os-release
        log "Дистрибутив: $PRETTY_NAME"
    fi
    
    # Ядро
    local kernel=$(uname -r)
    log "Версия ядра: $kernel"
    
    # Проверка загруженных модулей NVIDIA
    if lsmod | grep -q "^nvidia"; then
        warn "Модули NVIDIA уже загружены. Рекомендуется перезагрузка после патчинга"
    fi
}

# Создание директорий
create_directories() {
    log "Создание директорий..."
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$LIB_DIR/backups"
    mkdir -p "$LOG_DIR"
    mkdir -p "$BIN_DIR"
    
    # Установка прав
    chmod 755 "$INSTALL_DIR"
    chmod 755 "$LIB_DIR"
    chmod 755 "$LIB_DIR/backups"
    chmod 755 "$LOG_DIR"
}

# Копирование файлов
install_files() {
    log "Копирование файлов..."
    
    # Копирование основного проекта
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
    
    # Установка прав на скрипты
    chmod +x "$INSTALL_DIR/src"/*.py
    chmod +x "$INSTALL_DIR/tools"/*.sh
    chmod +x "$INSTALL_DIR/tools"/*.py
    
    # Создание символической ссылки
    ln -sf "$INSTALL_DIR/src/patcher.py" "$BIN_DIR/nvidia-patcher"
    
    log "Файлы установлены в: $INSTALL_DIR"
}

# Установка Python зависимостей
install_python_deps() {
    log "Установка Python зависимостей..."
    
    # Проверяем наличие pip
    if ! command -v pip3 >/dev/null 2>&1; then
        warn "pip3 не найден. Установка зависимостей пропущена"
        return
    fi
    
    # Создаем requirements.txt если нужно
    cat > "$INSTALL_DIR/requirements.txt" << EOF
# Базовые зависимости для NVIDIA Patcher
# (включены в стандартную библиотеку Python)
EOF
    
    # Установка зависимостей (пока пусто, так как используем только stdlib)
    # pip3 install -r "$INSTALL_DIR/requirements.txt" 2>/dev/null || warn "Ошибка установки зависимостей"
}

# Настройка логирования
setup_logging() {
    log "Настройка логирования..."
    
    # Создание конфигурации logrotate
    cat > "/etc/logrotate.d/$PROJECT_NAME" << EOF
$LOG_DIR/$PROJECT_NAME.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 root root
}
EOF
    
    # Создание лог файла
    touch "$LOG_DIR/$PROJECT_NAME.log"
    chmod 644 "$LOG_DIR/$PROJECT_NAME.log"
    chown root:root "$LOG_DIR/$PROJECT_NAME.log"
}

# Создание systemd сервиса (опционально)
create_systemd_service() {
    log "Создание systemd сервиса..."
    
    cat > "$SYSTEMD_DIR/$PROJECT_NAME.service" << EOF
[Unit]
Description=NVIDIA Driver Patcher Service
After=network.target
Wants=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 $INSTALL_DIR/src/patcher.py --detect
RemainAfterExit=yes
User=root
Group=root
TimeoutSec=300

[Install]
WantedBy=multi-user.target
EOF
    
    # Перезагрузка systemd
    systemctl daemon-reload
    
    info "Systemd сервис создан. Для автозапуска используйте:"
    info "  systemctl enable $PROJECT_NAME"
}

# Настройка прав SELinux (если активно)
setup_selinux() {
    if command -v getenforce >/dev/null 2>&1; then
        local selinux_status=$(getenforce 2>/dev/null || echo "Unknown")
        if [[ "$selinux_status" == "Enforcing" ]]; then
            warn "SELinux в режиме Enforcing. Могут потребоваться дополнительные настройки."
            warn "Выполните: semanage fcontext -a -t bin_t '$INSTALL_DIR/src/patcher.py'"
            warn "И затем: restorecon -v '$INSTALL_DIR/src/patcher.py'"
        fi
    fi
}

# Проверка установки
verify_installation() {
    log "Проверка установки..."
    
    local errors=0
    
    # Проверка файлов
    if [[ ! -f "$INSTALL_DIR/src/patcher.py" ]]; then
        error "Основной скрипт патчера не найден"
        ((errors++))
    fi
    
    if [[ ! -f "$BIN_DIR/nvidia-patcher" ]]; then
        error "Символическая ссылка не создана"
        ((errors++))
    fi
    
    # Проверка прав
    if [[ ! -x "$INSTALL_DIR/src/patcher.py" ]]; then
        error "Основной скрипт не является исполняемым"
        ((errors++))
    fi
    
    # Проверка работы скрипта
    if ! python3 "$INSTALL_DIR/src/patcher.py" --help >/dev/null 2>&1; then
        error "Основной скрипт не запускается"
        ((errors++))
    fi
    
    if [[ $errors -eq 0 ]]; then
        log "Установка успешно проверена"
    else
        error "Обнаружено $errors ошибок при установке"
    fi
}

# Показ информации об использовании
show_usage_info() {
    echo ""
    echo "=========================================="
    echo "Установка завершена успешно!"
    echo "=========================================="
    echo ""
    echo "Основные команды:"
    echo "  sudo nvidia-patcher --detect     # Обнаружить драйверы"
    echo "  sudo nvidia-patcher --patch      # Применить патч"
    echo "  sudo nvidia-patcher --rollback   # Откатить изменения"
    echo "  sudo nvidia-patcher --help       # Показать справку"
    echo ""
    echo "Полезные утилиты:"
    echo "  $INSTALL_DIR/tools/extract_driver.sh  # Извлечение драйвера"
    echo "  $INSTALL_DIR/tools/verify_patch.py    # Проверка патча"
    echo ""
    echo "Файлы конфигурации:"
    echo "  $INSTALL_DIR/                    # Основная директория"
    echo "  $LIB_DIR/backups/               # Резервные копии"
    echo "  $LOG_DIR/$PROJECT_NAME.log      # Лог файл"
    echo ""
    echo "Документация:"
    echo "  $INSTALL_DIR/README.md           # Основная документация"
    echo "  $INSTALL_DIR/docs/               # Дополнительная документация"
    echo ""
    warn "ВАЖНО: Перед использованием рекомендуется сделать резервную копию системы"
    warn "и прочитать документацию в $INSTALL_DIR/README.md"
}

# Функция деинсталляции
uninstall() {
    log "Деинсталляция $PROJECT_NAME..."
    
    # Остановка сервиса
    if systemctl is-enabled "$PROJECT_NAME" 2>/dev/null; then
        systemctl stop "$PROJECT_NAME"
        systemctl disable "$PROJECT_NAME"
    fi
    
    # Удаление файлов
    rm -f "$SYSTEMD_DIR/$PROJECT_NAME.service"
    rm -f "$BIN_DIR/nvidia-patcher"
    rm -f "/etc/logrotate.d/$PROJECT_NAME"
    rm -rf "$INSTALL_DIR"
    rm -rf "$LIB_DIR"
    
    # Перезагрузка systemd
    systemctl daemon-reload
    
    log "Деинсталляция завершена"
}

# Функция помощи
show_help() {
    cat << EOF
Инсталляционный скрипт для Linux NVIDIA Patcher

Использование: $0 [опции]

Опции:
  install     Установить патчер (по умолчанию)
  uninstall   Удалить патчер
  help        Показать эту справку

Примеры:
  sudo $0              # Установка
  sudo $0 install       # Установка
  sudo $0 uninstall     # Удаление
  sudo $0 help          # Справка

Требования:
  - Права суперпользователя
  - Linux x86_64
  - Python 3.6+
  - Утилиты: patch, grep, awk, find
EOF
}

# Основная функция
main() {
    local action="install"
    
    # Парсинг аргументов
    if [[ $# -gt 0 ]]; then
        case "$1" in
            uninstall)
                action="uninstall"
                ;;
            install)
                action="install"
                ;;
            help|--help|-h)
                show_help
                exit 0
                ;;
            *)
                error "Неизвестная опция: $1. Используйте --help для справки."
                ;;
        esac
    fi
    
    echo "=========================================="
    echo "Linux NVIDIA Patcher Installer"
    echo "=========================================="
    echo ""
    
    if [[ "$action" == "uninstall" ]]; then
        check_root
        uninstall
        echo ""
        echo "Деинсталляция завершена!"
        exit 0
    fi
    
    # Установка
    check_root
    check_dependencies
    check_system
    create_directories
    install_files
    install_python_deps
    setup_logging
    create_systemd_service
    setup_selinux
    verify_installation
    show_usage_info
}

# Запуск
main "$@"
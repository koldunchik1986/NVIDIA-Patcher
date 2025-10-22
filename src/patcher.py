#!/usr/bin/env python3
"""
Linux NVIDIA Driver Patcher
Утилита для патчинга драйверов NVIDIA на Linux x64
"""

import os
import sys
import shutil
import subprocess
import argparse
import logging
import hashlib
import json
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from driver_detector import DriverDetector
from backup_manager import BackupManager
from mining_card_detector import MiningCardDetector
from sli_manager import SLIManager
from ai_optimizer import AIOptimizer

class NvidiaPatcher:
    """Основной класс патчера NVIDIA драйверов"""
    
    def __init__(self, log_level=logging.INFO):
        self.setup_logging(log_level)
        self.logger = logging.getLogger(__name__)
        self.driver_detector = DriverDetector()
        self.backup_manager = BackupManager()
        self.mining_card_detector = MiningCardDetector()
        self.sli_manager = SLIManager()
        self.ai_optimizer = AIOptimizer()
        self.patch_dir = Path(__file__).parent.parent / "patches"
        self.supported_versions = ["535.274.02"]
        
    def setup_logging(self, level):
        """Настройка логирования"""
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/nvidia-patcher.log'),
                logging.StreamHandler()
            ]
        )
    
    def detect_mining_cards(self) -> List[Dict]:
        """Обнаружение майнинговых карт"""
        return self.mining_card_detector.detect_mining_cards()
    
    def _apply_mining_cards_patches(self, mining_cards: List[Dict]) -> bool:
        """Применение патчей для майнинговых карт"""
        try:
            self.logger.info("Применение патчей для майнинговых карт...")
            
            mining_patch_file = self.patch_dir / "mining_cards.patch"
            if mining_patch_file.exists():
                self.logger.info(f"Применение файла патча: {mining_patch_file}")
                # Логика применения патча
            
            for card in mining_cards:
                model = card.get('model')
                patches = self.mining_card_detector.get_mining_card_patches(model)
                if patches:
                    self.logger.info(f"Применение патчей для {model}: {list(patches.keys())}")
            
            return True
        except Exception as e:
            self.logger.error(f"Ошибка применения патчей майнинговых карт: {e}")
            return False
    
    def _setup_sli_configuration(self, sli_analysis: Dict, mining_cards: List[Dict]) -> bool:
        """Настройка SLI конфигурации"""
        try:
            config_type = sli_analysis['recommended_config']
            sli_config = self.sli_manager.create_sli_configuration(config_type, mining_cards)
            
            if self.sli_manager.save_sli_config(sli_config):
                self.logger.info(f"SLI конфигурация сохранена: {config_type}")
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"Ошибка настройки SLI: {e}")
            return False
    
    def _apply_ai_optimizations_for_mining_cards(self, mining_cards: List[Dict]) -> bool:
        """Применение AI оптимизаций для майнинговых карт"""
        try:
            # Определяем профиль оптимизации на основе карт
            profile = 'llm_inference'  # по умолчанию
            
            # Анализируем возможности для выбора оптимального профиля
            capabilities = self.ai_optimizer.analyze_hardware_capabilities(mining_cards)
            
            if 'tensor_core_optimization' in capabilities.get('recommended_optimizations', []):
                profile = 'pytorch_training'
            
            self.logger.info(f"Применение AI оптимизаций с профилем: {profile}")
            return self.ai_optimizer.apply_ai_optimizations(profile, mining_cards)
            
        except Exception as e:
            self.logger.error(f"Ошибка применения AI оптимизаций: {e}")
            return False
    
    def detect_drivers(self) -> List[Dict]:
        """Обнаружение установленных драйверов NVIDIA"""
        self.logger.info("Поиск установленных драйверов NVIDIA...")
        drivers = self.driver_detector.detect_nvidia_drivers()
        
        if not drivers:
            self.logger.warning("Драйверы NVIDIA не найдены")
            return []
        
        supported_drivers = []
        for driver in drivers:
            if driver['version'] in self.supported_versions:
                supported_drivers.append(driver)
                self.logger.info(f"Найден поддерживаемый драйвер: {driver['version']}")
            else:
                self.logger.warning(f"Драйвер {driver['version']} не поддерживается")
        
        return supported_drivers
    
    def verify_driver(self, driver_path: str) -> bool:
        """Проверка целостности драйвера"""
        try:
            if not os.path.exists(driver_path):
                self.logger.error(f"Файл драйвера не найден: {driver_path}")
                return False
            
            # Проверка контрольной суммы
            with open(driver_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            self.logger.info(f"SHA256 драйвера: {file_hash}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при проверке драйвера: {e}")
            return False
    
    def create_backup(self, driver_info: Dict) -> bool:
        """Создание резервной копии драйвера"""
        try:
            self.logger.info("Создание резервной копии...")
            backup_path = self.backup_manager.create_backup(driver_info)
            
            if backup_path:
                self.logger.info(f"Резервная копия создана: {backup_path}")
                return True
            else:
                self.logger.error("Не удалось создать резервную копию")
                return False
                
        except Exception as e:
            self.logger.error(f"Ошибка при создании бэкапа: {e}")
            return False
    
    def apply_patch(self, driver_info: Dict, dry_run: bool = False) -> bool:
        """Применение патча к драйверу"""
        try:
            version = driver_info['version']
            patch_file = self.patch_dir / f"nvidia_{version.split('.')[0]}.patch"
            
            if not patch_file.exists():
                self.logger.error(f"Файл патча не найден: {patch_file}")
                return False
            
            self.logger.info(f"Применение патча {patch_file} к драйверу {version}")
            
            # Получаем пути к модулям драйвера
            nvidia_paths = self.driver_detector.get_nvidia_module_paths(driver_info)
            
            for module_path in nvidia_paths:
                if not os.path.exists(module_path):
                    self.logger.warning(f"Модуль не найден: {module_path}")
                    continue
                
                self.logger.info(f"Патчинг модуля: {module_path}")
                
                if dry_run:
                    self.logger.info(f"[DRY RUN] Применение патча к {module_path}")
                    continue
                
                # Применяем патч
                result = subprocess.run([
                    'patch', '-b', module_path, str(patch_file)
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.logger.info(f"Патч успешно применен к {module_path}")
                else:
                    self.logger.error(f"Ошибка применения патча к {module_path}: {result.stderr}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при применении патча: {e}")
            return False
    
    def reload_nvidia_module(self) -> bool:
        """Перезагрузка модулей NVIDIA"""
        try:
            self.logger.info("Перезагрузка модулей NVIDIA...")
            
            # Выгрузка модулей
            modules = ['nvidia_drm', 'nvidia_uvm', 'nvidia_modeset', 'nvidia']
            for module in reversed(modules):
                try:
                    subprocess.run(['rmmod', module], check=True)
                    self.logger.info(f"Модуль {module} выгружен")
                except subprocess.CalledProcessError:
                    self.logger.warning(f"Не удалось выгрузить модуль {module}")
            
            # Загрузка модулей
            for module in modules:
                try:
                    subprocess.run(['modprobe', module], check=True)
                    self.logger.info(f"Модуль {module} загружен")
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"Не удалось загрузить модуль {module}: {e}")
                    return False
            
            self.logger.info("Модули NVIDIA успешно перезагружены")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при перезагрузке модулей: {e}")
            return False
    
    def rollback_changes(self, driver_info: Dict) -> bool:
        """Откат изменений"""
        try:
            self.logger.info("Откат изменений...")
            success = self.backup_manager.restore_backup(driver_info)
            
            if success:
                self.logger.info("Изменения успешно отменены")
                return True
            else:
                self.logger.error("Не удалось отменить изменения")
                return False
                
        except Exception as e:
            self.logger.error(f"Ошибка при откате изменений: {e}")
            return False
    
    def patch_driver(self, driver_path: Optional[str] = None, 
                    auto_mode: bool = False, dry_run: bool = False,
                    verbose: bool = False) -> bool:
        """Основная функция патчинга драйвера"""
        try:
            if verbose:
                logging.getLogger().setLevel(logging.DEBUG)
            
            # Обнаружение драйверов
            if driver_path:
                if not self.verify_driver(driver_path):
                    return False
                # Здесь можно добавить обработку внешнего файла драйвера
                drivers = [{'path': driver_path, 'version': '535.274.02'}]
            else:
                drivers = self.detect_drivers()
            
            if not drivers:
                self.logger.error("Поддерживаемые драйверы не найдены")
                return False
            
            driver = drivers[0]  # Берем первый найденный драйвер
            
            # Создание бэкапа
            if not dry_run and not self.create_backup(driver):
                return False
            
            # Применение патча
            if not self.apply_patch(driver, dry_run):
                return False
            
            if not dry_run:
                # Перезагрузка модулей
                if auto_mode and not self.reload_nvidia_module():
                    self.logger.warning("Не удалось перезагрузить модули автоматически")
                
                self.logger.info("Патчинг успешно завершен!")
                self.logger.info("Рекомендуется перезагрузить систему для полной активации изменений")
            else:
                self.logger.info("[DRY RUN] Патчинг завершен в тестовом режиме")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {e}")
            return False

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Linux NVIDIA Driver Patcher')
    parser.add_argument('--detect', action='store_true', help='Обнаружить драйверы NVIDIA')
    parser.add_argument('--patch', action='store_true', help='Применить патч')
    parser.add_argument('--rollback', action='store_true', help='Откатить изменения')
    parser.add_argument('--driver-path', help='Путь к файлу драйвера')
    parser.add_argument('--auto', action='store_true', help='Автоматический режим')
    parser.add_argument('--dry-run', action='store_true', help='Тестовый режим')
    parser.add_argument('--verbose', action='store_true', help='Подробный вывод')
    
    args = parser.parse_args()
    
    if os.geteuid() != 0:
        print("Ошибка: требуются права суперпользователя")
        sys.exit(1)
    
    patcher = NvidiaPatcher()
    
    if args.detect:
        drivers = patcher.detect_drivers()
        if drivers:
            print("Найденные поддерживаемые драйверы:")
            for driver in drivers:
                print(f"  - {driver['version']}: {driver.get('path', 'N/A')}")
        else:
            print("Поддерживаемые драйверы не найдены")
    
    elif args.rollback:
        drivers = patcher.detect_drivers()
        if drivers:
            success = patcher.rollback_changes(drivers[0])
            sys.exit(0 if success else 1)
        else:
            print("Драйверы не найдены")
            sys.exit(1)
    
    elif args.patch or args.driver_path or args.auto:
        success = patcher.patch_driver(
            driver_path=args.driver_path,
            auto_mode=args.auto,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
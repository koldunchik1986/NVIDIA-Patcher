#!/usr/bin/env python3
"""
Менеджер резервных копий для драйверов NVIDIA
"""

import os
import shutil
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Optional, List

class BackupManager:
    """Класс для управления резервными копиями"""
    
    def __init__(self, backup_dir: str = "/var/lib/nvidia-patcher/backups"):
        self.logger = logging.getLogger(__name__)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.backup_index = self.backup_dir / "backup_index.json"
        self.load_backup_index()
    
    def load_backup_index(self):
        """Загрузка индекса бэкапов"""
        try:
            if self.backup_index.exists():
                with open(self.backup_index, 'r') as f:
                    self.backup_data = json.load(f)
            else:
                self.backup_data = {}
        except Exception as e:
            self.logger.error(f"Ошибка загрузки индекса бэкапов: {e}")
            self.backup_data = {}
    
    def save_backup_index(self):
        """Сохранение индекса бэкапов"""
        try:
            with open(self.backup_index, 'w') as f:
                json.dump(self.backup_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения индекса бэкапов: {e}")
    
    def create_backup(self, driver_info: Dict) -> Optional[str]:
        """Создание резервной копии драйвера"""
        try:
            version = driver_info['version']
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"nvidia_{version}_{timestamp}"
            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(parents=True, exist_ok=True)
            
            self.logger.info(f"Создание бэкапа в: {backup_path}")
            
            # Копирование файлов драйвера
            from driver_detector import DriverDetector
            detector = DriverDetector()
            module_paths = detector.get_nvidia_module_paths(driver_info)
            
            backed_up_files = []
            success_count = 0
            
            for module_path in module_paths:
                try:
                    if os.path.exists(module_path):
                        filename = os.path.basename(module_path)
                        backup_file = backup_path / filename
                        
                        # Копирование файла
                        shutil.copy2(module_path, backup_file)
                        
                        # Сохранение информации о файле
                        backed_up_files.append({
                            'original': module_path,
                            'backup': str(backup_file),
                            'size': os.path.getsize(module_path),
                            'checksum': self._calculate_checksum(module_path)
                        })
                        
                        success_count += 1
                        self.logger.info(f"Скопирован: {module_path}")
                    
                except Exception as e:
                    self.logger.error(f"Ошибка копирования {module_path}: {e}")
            
            # Сохранение конфигурационных файлов
            config_files = self._backup_config_files(backup_path)
            
            # Обновление индекса
            self.backup_data[backup_name] = {
                'version': version,
                'timestamp': timestamp,
                'files': backed_up_files,
                'config_files': config_files,
                'driver_info': driver_info,
                'created_at': datetime.datetime.now().isoformat()
            }
            
            self.save_backup_index()
            
            if success_count > 0:
                self.logger.info(f"Бэкап успешно создан: {backup_name}")
                return str(backup_path)
            else:
                self.logger.error("Не удалось скопировать ни одного файла")
                return None
                
        except Exception as e:
            self.logger.error(f"Ошибка создания бэкапа: {e}")
            return None
    
    def _backup_config_files(self, backup_path: Path) -> List[str]:
        """Резервное копирование конфигурационных файлов"""
        config_files = []
        config_paths = [
            '/etc/modprobe.d/nvidia.conf',
            '/etc/modprobe.d/nvidia-drm.conf',
            '/etc/X11/xorg.conf',
            '/etc/X11/xorg.conf.d/nvidia.conf',
            '/usr/share/X11/xorg.conf.d/nvidia.conf'
        ]
        
        config_backup_dir = backup_path / "config"
        config_backup_dir.mkdir(exist_ok=True)
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                try:
                    filename = os.path.basename(config_path)
                    backup_config = config_backup_dir / filename
                    shutil.copy2(config_path, backup_config)
                    config_files.append({
                        'original': config_path,
                        'backup': str(backup_config)
                    })
                    self.logger.info(f"Скопирован конфиг: {config_path}")
                except Exception as e:
                    self.logger.error(f"Ошибка копирования конфига {config_path}: {e}")
        
        return config_files
    
    def restore_backup(self, driver_info: Dict) -> bool:
        """Восстановление из резервной копии"""
        try:
            version = driver_info['version']
            
            # Поиск последнего бэкапа для этой версии
            latest_backup = self._find_latest_backup(version)
            
            if not latest_backup:
                self.logger.error(f"Бэкап для версии {version} не найден")
                return False
            
            backup_info = self.backup_data[latest_backup]
            backup_path = self.backup_dir / latest_backup
            
            self.logger.info(f"Восстановление из бэкапа: {backup_path}")
            
            # Восстановление файлов
            success_count = 0
            for file_info in backup_info['files']:
                original_path = file_info['original']
                backup_path_file = file_info['backup']
                
                try:
                    if os.path.exists(backup_path_file):
                        # Проверка контрольной суммы
                        current_checksum = self._calculate_checksum(backup_path_file)
                        if current_checksum == file_info['checksum']:
                            shutil.copy2(backup_path_file, original_path)
                            success_count += 1
                            self.logger.info(f"Восстановлен: {original_path}")
                        else:
                            self.logger.warning(f"Несовпадение контрольной суммы: {original_path}")
                    else:
                        self.logger.warning(f"Файл бэкапа не найден: {backup_path_file}")
                        
                except Exception as e:
                    self.logger.error(f"Ошибка восстановления {original_path}: {e}")
            
            # Восстановление конфигурационных файлов
            for config_info in backup_info.get('config_files', []):
                try:
                    original_config = config_info['original']
                    backup_config = config_info['backup']
                    
                    if os.path.exists(backup_config):
                        shutil.copy2(backup_config, original_config)
                        self.logger.info(f"Восстановлен конфиг: {original_config}")
                        
                except Exception as e:
                    self.logger.error(f"Ошибка восстановления конфига: {e}")
            
            if success_count > 0:
                self.logger.info(f"Восстановлено файлов: {success_count}")
                return True
            else:
                self.logger.error("Не удалось восстановить ни одного файла")
                return False
                
        except Exception as e:
            self.logger.error(f"Ошибка восстановления бэкапа: {e}")
            return False
    
    def _find_latest_backup(self, version: str) -> Optional[str]:
        """Поиск последнего бэкапа для указанной версии"""
        latest_backup = None
        latest_timestamp = None
        
        for backup_name, backup_info in self.backup_data.items():
            if backup_info['version'] == version:
                timestamp = backup_info.get('timestamp', '')
                if timestamp and (latest_timestamp is None or timestamp > latest_timestamp):
                    latest_backup = backup_name
                    latest_timestamp = timestamp
        
        return latest_backup
    
    def list_backups(self) -> List[Dict]:
        """Список доступных бэкапов"""
        backups = []
        
        for backup_name, backup_info in self.backup_data.items():
            backups.append({
                'name': backup_name,
                'version': backup_info['version'],
                'timestamp': backup_info['timestamp'],
                'created_at': backup_info.get('created_at'),
                'files_count': len(backup_info.get('files', [])),
                'path': str(self.backup_dir / backup_name)
            })
        
        return sorted(backups, key=lambda x: x['timestamp'], reverse=True)
    
    def delete_backup(self, backup_name: str) -> bool:
        """Удаление бэкапа"""
        try:
            if backup_name not in self.backup_data:
                self.logger.error(f"Бэкап {backup_name} не найден")
                return False
            
            backup_path = self.backup_dir / backup_name
            
            # Удаление директории бэкапа
            if backup_path.exists():
                shutil.rmtree(backup_path)
            
            # Удаление из индекса
            del self.backup_data[backup_name]
            self.save_backup_index()
            
            self.logger.info(f"Бэкап {backup_name} удален")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка удаления бэкапа {backup_name}: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count: int = 5) -> int:
        """Очистка старых бэкапов"""
        try:
            backups = self.list_backups()
            
            if len(backups) <= keep_count:
                return 0
            
            # Удаление самых старых бэкапов
            to_delete = backups[keep_count:]
            deleted_count = 0
            
            for backup in to_delete:
                if self.delete_backup(backup['name']):
                    deleted_count += 1
            
            self.logger.info(f"Удалено старых бэкапов: {deleted_count}")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Ошибка очистки бэкапов: {e}")
            return 0
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Вычисление контрольной суммы файла"""
        try:
            import hashlib
            hash_sha256 = hashlib.sha256()
            
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            
            return hash_sha256.hexdigest()
            
        except Exception as e:
            self.logger.error(f"Ошибка вычисления контрольной суммы {file_path}: {e}")
            return ""
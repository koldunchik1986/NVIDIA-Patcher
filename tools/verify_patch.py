#!/usr/bin/env python3
"""
Утилита для проверки применения патчей к драйверам NVIDIA
"""

import os
import sys
import struct
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class PatchVerifier:
    """Класс для проверки патчей"""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.patch_signatures = {
            '535.274.02': {
                'magic_bytes': b'NVPT\x01\x00\x00\x00',
                'patch_offsets': [0x00123456, 0x00123ABC, 0x00123DEF],
                'expected_changes': [
                    {'offset': 0x00123456, 'original': b'\x85\xC0', 'patched': b'\x90\x90'},
                    {'offset': 0x00123ABC, 'original': b'\x75\x0A', 'patched': b'\x31\xC0\xC3'},
                ]
            }
        }
    
    def _setup_logging(self):
        """Настройка логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def verify_module(self, module_path: str, driver_version: str = "535.274.02") -> Dict:
        """Проверка модуля на наличие патча"""
        result = {
            'module_path': module_path,
            'exists': False,
            'patched': False,
            'valid': False,
            'details': {},
            'errors': []
        }
        
        try:
            if not os.path.exists(module_path):
                result['errors'].append(f"Файл не существует: {module_path}")
                return result
            
            result['exists'] = True
            result['details'] = self._analyze_module(module_path)
            
            # Проверка сигнатуры патча
            if self._check_patch_signature(module_path, driver_version):
                result['patched'] = True
                result['valid'] = True
                self.logger.info(f"Модуль {module_path} успешно пропатчен")
            else:
                result['patched'] = False
                self.logger.warning(f"Модуль {module_path} не пропатчен или патч поврежден")
            
        except Exception as e:
            result['errors'].append(f"Ошибка проверки модуля: {e}")
            self.logger.error(f"Ошибка проверки {module_path}: {e}")
        
        return result
    
    def _analyze_module(self, module_path: str) -> Dict:
        """Анализ модуля"""
        details = {
            'size': 0,
            'sha256': '',
            'magic': '',
            'architecture': '',
            'sections': []
        }
        
        try:
            # Базовая информация
            stat = os.stat(module_path)
            details['size'] = stat.st_size
            
            # Контрольная сумма
            with open(module_path, 'rb') as f:
                content = f.read()
                details['sha256'] = hashlib.sha256(content).hexdigest()
            
            # Magic bytes
            with open(module_path, 'rb') as f:
                magic = f.read(16)
                details['magic'] = magic.hex()
            
            # Архитектура (из ELF header)
            if content.startswith(b'\x7fELF'):
                # Упрощенный анализ ELF
                details['architecture'] = 'x86_64' if struct.unpack('<H', content[18:20])[0] == 62 else 'x86'
            
            # Поиск секций
            details['sections'] = self._find_sections(content)
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа модуля: {e}")
        
        return details
    
    def _find_sections(self, content: bytes) -> List[str]:
        """Поиск секций в модуле"""
        sections = []
        
        # Простая эвристика для поиска секций
        section_patterns = [
            b'.text',
            b'.data',
            b'.rodata',
            b'.bss',
            b'.symtab',
            b'.strtab'
        ]
        
        for pattern in section_patterns:
            if pattern in content:
                sections.append(pattern.decode('ascii'))
        
        return sections
    
    def _check_patch_signature(self, module_path: str, driver_version: str) -> bool:
        """Проверка сигнатуры патча"""
        try:
            with open(module_path, 'rb') as f:
                content = f.read()
            
            # Проверка magic bytes патча
            signature_info = self.patch_signatures.get(driver_version)
            if not signature_info:
                self.logger.warning(f"Информация о патче для версии {driver_version} не найдена")
                return False
            
            # Поиск magic bytes
            if signature_info['magic_bytes'] in content:
                self.logger.info(f"Magic bytes патча найдены в {module_path}")
                
                # Дополнительная проверка патчей
                return self._verify_patch_details(content, signature_info)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка проверки сигнатуры: {e}")
            return False
    
    def _verify_patch_details(self, content: bytes, signature_info: Dict) -> bool:
        """Детальная проверка патча"""
        try:
            for change in signature_info.get('expected_changes', []):
                offset = change['offset']
                original = change['original']
                patched = change['patched']
                
                # Проверка, что оригинальные байты заменены на патченые
                if offset + len(patched) <= len(content):
                    current_bytes = content[offset:offset + len(patched)]
                    if current_bytes != patched:
                        self.logger.warning(f"Патч не применен по смещению {offset}")
                        return False
                else:
                    self.logger.warning(f"Смещение {offset} выходит за пределы файла")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка детальной проверки: {e}")
            return False
    
    def verify_driver_installation(self, driver_version: str = "535.274.02") -> Dict:
        """Проверка полной установки драйвера"""
        result = {
            'driver_version': driver_version,
            'modules_checked': 0,
            'modules_patched': 0,
            'modules_valid': 0,
            'modules': [],
            'overall_status': 'unknown'
        }
        
        # Поиск модулей NVIDIA
        module_paths = self._find_nvidia_modules()
        
        for module_path in module_paths:
            module_result = self.verify_module(module_path, driver_version)
            result['modules'].append(module_result)
            result['modules_checked'] += 1
            
            if module_result['patched']:
                result['modules_patched'] += 1
            
            if module_result['valid']:
                result['modules_valid'] += 1
        
        # Определение общего статуса
        if result['modules_checked'] == 0:
            result['overall_status'] = 'not_found'
        elif result['modules_valid'] == result['modules_checked']:
            result['overall_status'] = 'fully_patched'
        elif result['modules_patched'] > 0:
            result['overall_status'] = 'partially_patched'
        else:
            result['overall_status'] = 'not_patched'
        
        return result
    
    def _find_nvidia_modules(self) -> List[str]:
        """Поиск модулей NVIDIA"""
        module_paths = []
        search_paths = [
            '/lib/modules/',
            '/usr/lib/x86_64-linux-gnu/',
            '/usr/lib64/'
        ]
        
        # Текущее ядро
        import subprocess
        try:
            kernel_release = subprocess.check_output(['uname', '-r'], text=True).strip()
        except:
            kernel_release = ""
        
        # Поиск модулей
        for base_path in search_paths:
            if base_path == '/lib/modules/' and kernel_release:
                search_path = f"{base_path}{kernel_release}/"
            else:
                search_path = base_path
            
            try:
                for root, dirs, files in os.walk(search_path):
                    for file in files:
                        if file.startswith('nvidia') and file.endswith('.ko'):
                            full_path = os.path.join(root, file)
                            if os.path.exists(full_path):
                                module_paths.append(full_path)
            except (PermissionError, OSError):
                continue
        
        # Поиск в текущей директории проекта
        project_modules = Path(__file__).parent.parent / "modules"
        if project_modules.exists():
            for module_file in project_modules.glob("nvidia*.ko"):
                module_paths.append(str(module_file))
        
        return list(set(module_paths))  # Удаление дубликатов
    
    def generate_report(self, verification_result: Dict, output_file: Optional[str] = None) -> str:
        """Генерация отчета о проверке"""
        report = []
        report.append("=" * 60)
        report.append("ОТЧЕТ О ПРОВЕРКЕ ПАТЧА NVIDIA ДРАЙВЕРА")
        report.append("=" * 60)
        report.append("")
        
        # Общая информация
        report.append(f"Версия драйвера: {verification_result['driver_version']}")
        report.append(f"Проверено модулей: {verification_result['modules_checked']}")
        report.append(f"Пропатчено модулей: {verification_result['modules_patched']}")
        report.append(f"Валидных модулей: {verification_result['modules_valid']}")
        report.append(f"Общий статус: {verification_result['overall_status']}")
        report.append("")
        
        # Детальная информация по модулям
        report.append("ДЕТАЛИ ПО МОДУЛЯМ:")
        report.append("-" * 40)
        
        for i, module in enumerate(verification_result['modules'], 1):
            report.append(f"{i}. {module['module_path']}")
            report.append(f"   Существует: {'Да' if module['exists'] else 'Нет'}")
            report.append(f"   Пропатчен: {'Да' if module['patched'] else 'Нет'}")
            report.append(f"   Валиден: {'Да' if module['valid'] else 'Нет'}")
            
            if module['details']:
                details = module['details']
                report.append(f"   Размер: {details.get('size', 0)} байт")
                if details.get('sha256'):
                    report.append(f"   SHA256: {details['sha256'][:16]}...")
                if details.get('architecture'):
                    report.append(f"   Архитектура: {details['architecture']}")
            
            if module['errors']:
                report.append("   Ошибки:")
                for error in module['errors']:
                    report.append(f"     - {error}")
            
            report.append("")
        
        # Рекомендации
        report.append("РЕКОМЕНДАЦИИ:")
        report.append("-" * 20)
        
        status = verification_result['overall_status']
        if status == 'fully_patched':
            report.append("✓ Все модули успешно пропатчены и валидны")
        elif status == 'partially_patched':
            report.append("⚠ Некоторые модули пропатчены, но есть проблемы")
            report.append("  Рекомендуется повторить патчинг")
        elif status == 'not_patched':
            report.append("✗ Модули не пропатчены")
            report.append("  Необходимо применить патч")
        elif status == 'not_found':
            report.append("✗ Модули NVIDIA не найдены")
            report.append("  Убедитесь, что драйвер установлен")
        
        report_text = "\n".join(report)
        
        # Сохранение в файл
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(report_text)
                self.logger.info(f"Отчет сохранен в: {output_file}")
            except Exception as e:
                self.logger.error(f"Ошибка сохранения отчета: {e}")
        
        return report_text

def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Проверка патчей драйверов NVIDIA')
    parser.add_argument('--module', help='Проверить конкретный модуль')
    parser.add_argument('--version', default='535.274.02', help='Версия драйвера')
    parser.add_argument('--output', help='Файл для сохранения отчета')
    parser.add_argument('--json', action='store_true', help='Вывод в JSON формате')
    parser.add_argument('--verbose', action='store_true', help='Подробный вывод')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    verifier = PatchVerifier()
    
    if args.module:
        # Проверка конкретного модуля
        result = verifier.verify_module(args.module, args.version)
        
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            report = verifier.generate_report({'modules': [result], 'overall_status': 'custom'})
            print(report)
    
    else:
        # Полная проверка драйвера
        result = verifier.verify_driver_installation(args.version)
        
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            report = verifier.generate_report(result, args.output)
            print(report)

if __name__ == '__main__':
    main()
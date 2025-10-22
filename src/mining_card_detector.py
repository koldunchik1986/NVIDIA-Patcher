#!/usr/bin/env python3
"""
Модуль для обнаружения и идентификации майнинговых видеокарт NVIDIA
P106-100, P104-100, P102, P106-090 и других
"""

import os
import re
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Optional
import json

class MiningCardDetector:
    """Детектор майнинговых видеокарт NVIDIA"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # База данных майнинговых карт
        self.mining_cards = {
            # P104-100 (GTX 1080)
            'P104-100': {
                'device_id': '1B80',
                'subsystem_vendor_id': ['1458', '1462', '10DE'],  # Gigabyte, MSI, NVIDIA
                'chip': 'GP104',
                'equivalent_gaming': 'GTX 1080',
                'memory_size': 8192,  # MB
                'tensor_cores': False,
                'sli_support': True,
                'patch_required': True
            },
            
            # P106-100 (GTX 1060)
            'P106-100': {
                'device_id': '1C02',
                'subsystem_vendor_id': ['1458', '1462', '10DE', '1569'],  # Gigabyte, MSI, NVIDIA, Palit
                'chip': 'GP106',
                'equivalent_gaming': 'GTX 1060 6GB',
                'memory_size': 6144,
                'tensor_cores': False,
                'sli_support': False,
                'patch_required': True
            },
            
            # P102-100 (GTX 1070/Ti)
            'P102-100': {
                'device_id': '1BA1',
                'subsystem_vendor_id': ['1458', '1462', '10DE'],
                'chip': 'GP102',
                'equivalent_gaming': 'GTX 1070 Ti',
                'memory_size': 8192,
                'tensor_cores': False,
                'sli_support': True,
                'patch_required': True
            },
            
            # P106-090 (GTX 1060 3GB)
            'P106-090': {
                'device_id': '1C03',
                'subsystem_vendor_id': ['1458', '1462', '10DE'],
                'chip': 'GP106',
                'equivalent_gaming': 'GTX 1060 3GB',
                'memory_size': 3072,
                'tensor_cores': False,
                'sli_support': False,
                'patch_required': True
            },
            
            # P104 (GTX 1080 Ti)
            'P104': {
                'device_id': '1B81',
                'subsystem_vendor_id': ['1458', '1462', '10DE'],
                'chip': 'GP104',
                'equivalent_gaming': 'GTX 1080 Ti',
                'memory_size': 11264,
                'tensor_cores': False,
                'sli_support': True,
                'patch_required': True
            },
            
            # Turing поколения (RTX 2060)
            'TU116': {
                'device_id': '1F08',
                'subsystem_vendor_id': ['1458', '1462', '10DE'],
                'chip': 'TU116',
                'equivalent_gaming': 'RTX 2060',
                'memory_size': 6144,
                'tensor_cores': True,
                'sli_support': False,
                'patch_required': True
            }
        }
    
    def detect_mining_cards(self) -> List[Dict]:
        """Обнаружение майнинговых карт в системе"""
        detected_cards = []
        
        try:
            # Метод 1: через lspci
            lspci_cards = self._detect_via_lspci()
            detected_cards.extend(lspci_cards)
            
            # Метод 2: через nvidia-smi (если драйвер уже загружен)
            if os.path.exists('/usr/bin/nvidia-smi'):
                smi_cards = self._detect_via_nvidia_smi()
                # Объединяем результаты, удаляя дубликаты
                detected_cards = self._merge_card_lists(detected_cards, smi_cards)
            
            # Метод 3: через sysfs
            sysfs_cards = self._detect_via_sysfs()
            detected_cards = self._merge_card_lists(detected_cards, sysfs_cards)
            
        except Exception as e:
            self.logger.error(f"Ошибка при обнаружении майнинговых карт: {e}")
        
        self.logger.info(f"Обнаружено майнинговых карт: {len(detected_cards)}")
        return detected_cards
    
    def _detect_via_lspci(self) -> List[Dict]:
        """Обнаружение через lspci"""
        cards = []
        
        try:
            result = subprocess.run(
                ['lspci', '-nn', '-D'],
                capture_output=True, text=True, timeout=10
            )
            
            for line in result.stdout.split('\n'):
                if 'VGA' in line or '3D' in line:
                    card_info = self._parse_lspci_line(line)
                    if card_info and card_info['is_mining']:
                        cards.append(card_info)
                        self.logger.info(f"Найдена майнинговая карта: {card_info['model']}")
        
        except Exception as e:
            self.logger.debug(f"lspci detection failed: {e}")
        
        return cards
    
    def _parse_lspci_line(self, line: str) -> Optional[Dict]:
        """Парсинг строки lspci"""
        try:
            # Пример строки:
            # 01:00.0 VGA compatible controller [0300]: NVIDIA Corporation GP104 [GeForce GTX 1080] [10de:1b80] (rev a1)
            
            # Извлечение PCI адреса
            pci_address = line.split()[0]
            
            # Извлечение ID устройства и вендора
            device_match = re.search(r'\[([0-9a-f]{4}):([0-9a-f]{4})\]', line)
            if not device_match:
                return None
            
            vendor_id = device_match.group(1).upper()
            device_id = device_match.group(2).upper()
            
            # Проверяем, является ли это NVIDIA
            if vendor_id != '10DE':
                return None
            
            # Ищем в базе данных майнинговых карт
            for model_name, model_info in self.mining_cards.items():
                if model_info['device_id'] == device_id:
                    return {
                        'pci_address': pci_address,
                        'vendor_id': vendor_id,
                        'device_id': device_id,
                        'model': model_name,
                        'chip': model_info['chip'],
                        'equivalent_gaming': model_info['equivalent_gaming'],
                        'memory_size': model_info['memory_size'],
                        'tensor_cores': model_info['tensor_cores'],
                        'sli_support': model_info['sli_support'],
                        'patch_required': model_info['patch_required'],
                        'is_mining': True,
                        'detection_method': 'lspci'
                    }
            
            return None
        
        except Exception as e:
            self.logger.debug(f"Error parsing lspci line: {e}")
            return None
    
    def _detect_via_nvidia_smi(self) -> List[Dict]:
        """Обнаружение через nvidia-smi"""
        cards = []
        
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=gpu_name,pci.bus_id,memory.total', '--format=csv,noheader'],
                capture_output=True, text=True, timeout=10
            )
            
            for line in result.stdout.split('\n'):
                if line.strip():
                    card_info = self._parse_nvidia_smi_line(line)
                    if card_info and card_info['is_mining']:
                        cards.append(card_info)
        
        except Exception as e:
            self.logger.debug(f"nvidia-smi detection failed: {e}")
        
        return cards
    
    def _parse_nvidia_smi_line(self, line: str) -> Optional[Dict]:
        """Парсинг строки nvidia-smi"""
        try:
            parts = line.split(',')
            if len(parts) < 3:
                return None
            
            name = parts[0].strip()
            pci_bus_id = parts[1].strip()
            memory_total = parts[2].strip()
            
            # Конвертация памяти в MB
            memory_mb = 0
            if 'MiB' in memory_total:
                memory_mb = int(memory_total.replace('MiB', '').strip())
            elif 'GiB' in memory_total:
                memory_mb = int(float(memory_total.replace('GiB', '').strip())) * 1024
            
            # Проверяем на майнинговые карты по имени
            for model_name, model_info in self.mining_cards.items():
                if model_name in name or model_info['chip'] in name:
                    return {
                        'pci_address': pci_bus_id,
                        'model': model_name,
                        'chip': model_info['chip'],
                        'equivalent_gaming': model_info['equivalent_gaming'],
                        'memory_size': model_info['memory_size'],
                        'detected_memory': memory_mb,
                        'tensor_cores': model_info['tensor_cores'],
                        'sli_support': model_info['sli_support'],
                        'patch_required': model_info['patch_required'],
                        'is_mining': True,
                        'detection_method': 'nvidia-smi'
                    }
            
            return None
        
        except Exception as e:
            self.logger.debug(f"Error parsing nvidia-smi line: {e}")
            return None
    
    def _detect_via_sysfs(self) -> List[Dict]:
        """Обнаружение через sysfs"""
        cards = []
        
        try:
            gpu_dirs = Path('/sys/bus/pci/devices').glob('*/gpu')
            
            for gpu_dir in gpu_dirs:
                if gpu_dir.is_dir():
                    card_info = self._parse_sysfs_gpu(gpu_dir)
                    if card_info and card_info['is_mining']:
                        cards.append(card_info)
        
        except Exception as e:
            self.logger.debug(f"sysfs detection failed: {e}")
        
        return cards
    
    def _parse_sysfs_gpu(self, gpu_dir: Path) -> Optional[Dict]:
        """Парсинг информации о GPU из sysfs"""
        try:
            # Чтение vendor и device ID
            vendor_file = gpu_dir.parent / 'vendor'
            device_file = gpu_dir.parent / 'device'
            
            if not (vendor_file.exists() and device_file.exists()):
                return None
            
            with open(vendor_file, 'r') as f:
                vendor_id = f.read().strip().replace('0x', '').upper()
            
            with open(device_file, 'r') as f:
                device_id = f.read().strip().replace('0x', '').upper()
            
            if vendor_id != '10DE':
                return None
            
            # Проверяем в базе данных
            for model_name, model_info in self.mining_cards.items():
                if model_info['device_id'] == device_id:
                    return {
                        'pci_address': gpu_dir.parent.name,
                        'vendor_id': vendor_id,
                        'device_id': device_id,
                        'model': model_name,
                        'chip': model_info['chip'],
                        'equivalent_gaming': model_info['equivalent_gaming'],
                        'memory_size': model_info['memory_size'],
                        'tensor_cores': model_info['tensor_cores'],
                        'sli_support': model_info['sli_support'],
                        'patch_required': model_info['patch_required'],
                        'is_mining': True,
                        'detection_method': 'sysfs'
                    }
            
            return None
        
        except Exception as e:
            self.logger.debug(f"Error parsing sysfs GPU: {e}")
            return None
    
    def _merge_card_lists(self, list1: List[Dict], list2: List[Dict]) -> List[Dict]:
        """Объединение списков карт без дубликатов"""
        merged = list1.copy()
        seen_addresses = {card['pci_address'] for card in list1}
        
        for card in list2:
            if card['pci_address'] not in seen_addresses:
                merged.append(card)
        
        return merged
    
    def get_mining_card_patches(self, model: str) -> Dict:
        """Получить информацию о необходимых патчах для модели"""
        if model not in self.mining_cards:
            return {}
        
        card_info = self.mining_cards[model]
        patches = {}
        
        # Базовые патчи для всех майнинговых карт
        patches['base'] = {
            'description': 'Базовые патчи для майнинговых карт',
            'operations': [
                {
                    'type': 'device_id_patch',
                    'original_id': card_info['device_id'],
                    'target_id': self._get_equivalent_device_id(model),
                    'description': f'ID модификация для {card_info["equivalent_gaming"]}'
                },
                {
                    'type': 'sli_enable',
                    'enabled': card_info['sli_support'],
                    'description': 'Разблокировка SLI поддержки'
                }
            ]
        }
        
        # Дополнительные патчи для AI workloads
        if card_info['tensor_cores']:
            patches['ai_optimization'] = {
                'description': 'Оптимизация для AI/ML нагрузок',
                'operations': [
                    {
                        'type': 'tensor_cores_enable',
                        'enabled': True,
                        'description': 'Активация Tensor Cores'
                    },
                    {
                        'type': 'cuda_optimization',
                        'operations': ['fp16_enable', 'tensorrt_enable'],
                        'description': 'CUDA оптимизации для ML'
                    }
                ]
            }
        
        # SLI патчи для смешанных конфигураций
        if card_info['sli_support']:
            patches['sli_mixed'] = {
                'description': 'SLI для смешанных конфигураций',
                'operations': [
                    {
                        'type': 'mixed_sli_patch',
                        'allow_different_cards': True,
                        'description': 'Разрешение SLI для разных моделей'
                    }
                ]
            }
        
        return patches
    
    def _get_equivalent_device_id(self, model: str) -> str:
        """Получить ID эквивалентной игровой карты"""
        equivalents = {
            'P104-100': '1B80',  # GTX 1080
            'P106-100': '1C02',  # GTX 1060 6GB
            'P102-100': '1BA1',  # GTX 1070 Ti
            'P106-090': '1C03',  # GTX 1060 3GB
            'P104': '1B81',      # GTX 1080 Ti
            'TU116': '1F08'      # RTX 2060
        }
        return equivalents.get(model, model)
    
    def validate_sli_configuration(self, cards: List[Dict]) -> Dict:
        """Валидация SLI конфигурации"""
        validation = {
            'sli_possible': False,
            'mixed_sli': False,
            'issues': [],
            'recommendations': []
        }
        
        if len(cards) < 2:
            validation['issues'].append('Недостаточно карт для SLI (минимум 2)')
            return validation
        
        # Проверяем поддержку SLI
        sli_cards = [card for card in cards if card['sli_support']]
        if len(sli_cards) < 2:
            validation['issues'].append('Недостаточно карт с поддержкой SLI')
            return validation
        
        # Проверяем одинаковость чипов для стандартного SLI
        chip_types = list(set(card['chip'] for card in sli_cards))
        
        if len(chip_types) == 1:
            validation['sli_possible'] = True
            validation['recommendations'].append('Стандартный SLI возможен')
        else:
            validation['mixed_sli'] = True
            validation['sli_possible'] = True
            validation['recommendations'].append('Возможен смешанный SLI (требуется патч)')
        
        # Проверяем память
        memory_sizes = [card['memory_size'] for card in sli_cards]
        if len(set(memory_sizes)) > 1:
            validation['issues'].append('Разный размер памяти у карт')
            validation['recommendations'].append('Рекомендуется использовать карты с одинаковым объемом памяти')
        
        return validation
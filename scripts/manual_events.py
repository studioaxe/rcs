#!/usr/bin/env python3
"""
Calendário Sync - Gestor de Eventos Manuais
Sistema para criar, gerenciar e exportar eventos manuais (bloqueios, ocultações, etc)

Tipos de Eventos:
- BLOCK_DATE: Bloquear data completa
- HIDE_EVENT: Ocultar evento específico (CLASS:PRIVATE)
- REMOVE_DATE: Remover período
- FORCE_AVAILABILITY: Forçar disponibilidade (TRANSP:TRANSPARENT)

Status: Production Ready
Versão: 1.0
Data: Janeiro 2026
"""

import json
import os
from datetime import datetime, date
from typing import List, Dict, Optional
from pathlib import Path
from icalendar import Calendar, Event
import uuid

class ManualCalendarManager:
    """Gestor de eventos manuais do calendário"""
    
    def __init__(self, data_dir: str = 'data'):
        """
        Inicializar gestor
        
        Args:
            data_dir: Diretório de armazenamento de dados
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.json_file = self.data_dir / 'manual_events.json'
        self.ics_file = self.data_dir / 'manual_calendar.ics'
        
        # Carregar eventos existentes
        self.events = self._load_events()
    
    # ========================================================================
    # CARREGAMENTO E ARMAZENAMENTO
    # ========================================================================
    
    def _load_events(self) -> List[Dict]:
        """Carregar eventos do ficheiro JSON"""
        if self.json_file.exists():
            try:
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('events', [])
            except Exception as e:
                print(f"Erro ao carregar eventos: {e}")
                return []
        return []
    
    def _save_events(self) -> None:
        """Guardar eventos em JSON"""
        try:
            data = {
                'version': '1.0',
                'last_modified': datetime.now().isoformat(),
                'events': self.events
            }
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erro ao guardar eventos: {e}")
    
    def _sync_to_ics(self) -> None:
        """Sincronizar eventos JSON para ICS"""
        try:
            cal = Calendar()
            cal.add('prodid', '-//Calendário Sync//Manual Events//PT')
            cal.add('version', '2.0')
            cal.add('method', 'PUBLISH')
            cal.add('x-wr-calname', 'Manual Calendar')
            cal.add('x-wr-timezone', 'Europe/Lisbon')
            
            for event in self.events:
                ical_event = Event()
                ical_event.add('uid', event['id'])
                ical_event.add('summary', f"[{event['type']}] {event['title']}")
                ical_event.add('description', event.get('description', ''))
                
                # Adicionar datas
                if 'date_start' in event:
                    ical_event.add('dtstart', datetime.fromisoformat(event['date_start']))
                if 'date_end' in event:
                    ical_event.add('dtend', datetime.fromisoformat(event['date_end']))
                
                # Adicionar tipo como property customizada
                ical_event.add('x-event-type', event['type'])
                
                # CLASS baseado no tipo
                if event['type'] == 'HIDE_EVENT':
                    ical_event.add('class', 'PRIVATE')
                elif event['type'] == 'FORCE_AVAILABILITY':
                    ical_event.add('transp', 'TRANSPARENT')
                
                ical_event.add('created', datetime.now())
                ical_event.add('last-modified', datetime.now())
                
                cal.add_component(ical_event)
            
            # Guardar ficheiro ICS
            with open(self.ics_file, 'wb') as f:
                f.write(cal.to_ical())
        
        except Exception as e:
            print(f"Erro ao sincronizar para ICS: {e}")
    
    # ========================================================================
    # CRUD - CREATE
    # ========================================================================
    
    def create_event(
        self,
        event_type: str,
        title: str,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        description: str = ''
    ) -> Dict:
        """
        Criar novo evento manual
        
        Args:
            event_type: Tipo de evento (BLOCK_DATE, HIDE_EVENT, REMOVE_DATE, FORCE_AVAILABILITY)
            title: Título do evento
            date_start: Data/hora início (ISO format)
            date_end: Data/hora fim (ISO format)
            description: Descrição
            
        Returns:
            Evento criado com ID
        """
        # Validar tipo
        valid_types = ['BLOCK_DATE', 'HIDE_EVENT', 'REMOVE_DATE', 'FORCE_AVAILABILITY']
        if event_type not in valid_types:
            raise ValueError(f"Tipo inválido: {event_type}")
        
        # Criar evento
        event = {
            'id': str(uuid.uuid4()),
            'type': event_type,
            'title': title,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        if date_start:
            event['date_start'] = date_start
        if date_end:
            event['date_end'] = date_end
        
        # Adicionar à lista
        self.events.append(event)
        self._save_events()
        self._sync_to_ics()
        
        return event
    
    # ========================================================================
    # CRUD - READ
    # ========================================================================
    
    def get_event(self, event_id: str) -> Optional[Dict]:
        """Obter evento por ID"""
        for event in self.events:
            if event['id'] == event_id:
                return event
        return None
    
    def get_all_events(self) -> List[Dict]:
        """Obter todos os eventos"""
        return self.events.copy()
    
    def get_events_by_type(self, event_type: str) -> List[Dict]:
        """Obter eventos por tipo"""
        return [e for e in self.events if e['type'] == event_type]
    
    def get_events_by_date(self, target_date: str) -> List[Dict]:
        """Obter eventos que afetam uma data específica"""
        target = datetime.fromisoformat(target_date).date()
        matching = []
        
        for event in self.events:
            if 'date_start' in event:
                start = datetime.fromisoformat(event['date_start']).date()
                if event['type'] == 'BLOCK_DATE' and start == target:
                    matching.append(event)
                elif 'date_end' in event:
                    end = datetime.fromisoformat(event['date_end']).date()
                    if start <= target <= end:
                        matching.append(event)
        
        return matching
    
    # ========================================================================
    # CRUD - UPDATE
    # ========================================================================
    
    def update_event(self, event_id: str, **kwargs) -> Optional[Dict]:
        """Atualizar evento existente"""
        event = self.get_event(event_id)
        if not event:
            return None
        
        # Campos atualizáveis
        updateable = ['title', 'description', 'date_start', 'date_end', 'type']
        for key, value in kwargs.items():
            if key in updateable:
                event[key] = value
        
        event['updated_at'] = datetime.now().isoformat()
        
        self._save_events()
        self._sync_to_ics()
        
        return event
    
    # ========================================================================
    # CRUD - DELETE
    # ========================================================================
    
    def delete_event(self, event_id: str) -> bool:
        """Deletar evento"""
        for i, event in enumerate(self.events):
            if event['id'] == event_id:
                self.events.pop(i)
                self._save_events()
                self._sync_to_ics()
                return True
        return False
    
    # ========================================================================
    # EXPORT/IMPORT
    # ========================================================================
    
    def export_to_json(self) -> str:
        """Exportar eventos para JSON string"""
        data = {
            'version': '1.0',
            'last_modified': datetime.now().isoformat(),
            'events': self.events
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def export_to_ics(self) -> str:
        """Exportar eventos para ICS string"""
        self._sync_to_ics()
        with open(self.ics_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    def import_from_json(self, json_data: str) -> bool:
        """Importar eventos de JSON string"""
        try:
            data = json.loads(json_data)
            self.events = data.get('events', [])
            self._save_events()
            self._sync_to_ics()
            return True
        except Exception as e:
            print(f"Erro ao importar JSON: {e}")
            return False
    
    def import_from_ics(self, ics_data: str) -> bool:
        """Importar eventos de ICS"""
        try:
            cal = Calendar.from_ical(ics_data)
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    event = {
                        'id': str(component.get('uid', str(uuid.uuid4()))),
                        'title': str(component.get('summary', 'Untitled')),
                        'description': str(component.get('description', '')),
                        'type': str(component.get('x-event-type', 'BLOCK_DATE')),
                        'date_start': str(component.get('dtstart', '')),
                        'date_end': str(component.get('dtend', '')),
                        'created_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    # Remover campos vazios
                    event = {k: v for k, v in event.items() if v}
                    self.events.append(event)
            
            self._save_events()
            return True
        except Exception as e:
            print(f"Erro ao importar ICS: {e}")
            return False
    
    # ========================================================================
    # UTILITÁRIOS
    # ========================================================================
    
    def get_statistics(self) -> Dict:
        """Obter estatísticas dos eventos"""
        stats = {
            'total': len(self.events),
            'by_type': {},
            'last_modified': None
        }
        
        for event_type in ['BLOCK_DATE', 'HIDE_EVENT', 'REMOVE_DATE', 'FORCE_AVAILABILITY']:
            count = len(self.get_events_by_type(event_type))
            if count > 0:
                stats['by_type'][event_type] = count
        
        if self.events:
            stats['last_modified'] = max(e.get('updated_at', '') for e in self.events)
        
        return stats
    
    def clear_all(self) -> None:
        """Limpar todos os eventos"""
        self.events = []
        self._save_events()
        self._sync_to_ics()


# ============================================================================
# EXEMPLO DE USO
# ============================================================================

if __name__ == '__main__':
    manager = ManualCalendarManager()
    
    # Criar alguns eventos de exemplo
    event1 = manager.create_event(
        'BLOCK_DATE',
        'Dia fechado',
        date_start='2026-02-02T00:00:00',
        description='Escritório fechado'
    )
    print(f"Evento criado: {event1['id']}")
    
    # Obter todos
    print(f"\nTotal de eventos: {len(manager.get_all_events())}")
    
    # Estatísticas
    stats = manager.get_statistics()
    print(f"\nEstatísticas: {stats}")
    
    # Exportar
    print(f"\nJSON:\n{manager.export_to_json()}")
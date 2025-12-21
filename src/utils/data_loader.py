"""
Data Loader for Custom Payment Data Upload
Supports CSV and JSON formats for proprietary payment datasets.
"""

import pandas as pd
import json
from typing import List, Optional
from datetime import datetime
from src.utils.models import ISO20022Message, PaymentType, PriorityTier
from src.message_generator.iso20022_generator import ISO20022Generator


class DataLoader:
    """Load and convert custom payment data to ISO20022Message format."""
    
    def __init__(self):
        self.generator = ISO20022Generator()
    
    def load_from_csv(self, file_content: bytes, filename: str) -> List[ISO20022Message]:
        """
        Load payment data from CSV file.
        
        Expected columns:
        - amount (required)
        - priority (optional: URGENT, HIGH, NORMAL, LOW)
        - timestamp (optional: ISO format)
        - msg_id (optional: auto-generated if not provided)
        - debtor_name (optional)
        - creditor_name (optional)
        - is_sovereign (optional: true/false)
        
        Args:
            file_content: CSV file content as bytes
            filename: Original filename
            
        Returns:
            List of ISO20022Message objects
        """
        try:
            df = pd.read_csv(pd.io.common.BytesIO(file_content))
            messages = []
            
            for idx, row in df.iterrows():
                amount = float(row.get('amount', 0))
                if amount <= 0:
                    continue
                
                priority_str = str(row.get('priority', 'NORMAL')).upper()
                try:
                    priority = PriorityTier[priority_str]
                except KeyError:
                    priority = PriorityTier.NORMAL
                
                timestamp_str = row.get('timestamp', None)
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(str(timestamp_str).replace('Z', '+00:00'))
                    except:
                        timestamp = datetime.now()
                else:
                    timestamp = datetime.now()
                
                msg_id = row.get('msg_id', None)
                debtor_name = row.get('debtor_name', None)
                creditor_name = row.get('creditor_name', None)
                is_sovereign = str(row.get('is_sovereign', 'false')).lower() == 'true'
                
                message = self.generator.generate_pacs008(
                    amount=amount,
                    priority=priority,
                    msg_id=msg_id,
                    debtor_name=debtor_name,
                    creditor_name=creditor_name,
                    is_sovereign=is_sovereign,
                    cre_dt_tm=timestamp
                )
                messages.append(message)
            
            return messages
            
        except Exception as e:
            raise ValueError(f"Error parsing CSV: {str(e)}")
    
    def load_from_json(self, file_content: bytes) -> List[ISO20022Message]:
        """
        Load payment data from JSON file.
        
        Expected format:
        [
            {
                "amount": 1000000.0,
                "priority": "URGENT",
                "timestamp": "2025-12-20T16:00:00Z",
                "msg_id": "CUSTOM-001",
                "debtor_name": "BANK_A",
                "creditor_name": "BANK_B",
                "is_sovereign": false
            },
            ...
        ]
        
        Args:
            file_content: JSON file content as bytes
            
        Returns:
            List of ISO20022Message objects
        """
        try:
            data = json.loads(file_content.decode('utf-8'))
            messages = []
            
            if not isinstance(data, list):
                data = [data]
            
            for item in data:
                amount = float(item.get('amount', 0))
                if amount <= 0:
                    continue
                
                priority_str = str(item.get('priority', 'NORMAL')).upper()
                try:
                    priority = PriorityTier[priority_str]
                except KeyError:
                    priority = PriorityTier.NORMAL
                
                timestamp_str = item.get('timestamp', None)
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(str(timestamp_str).replace('Z', '+00:00'))
                    except:
                        timestamp = datetime.now()
                else:
                    timestamp = datetime.now()
                
                message = self.generator.generate_pacs008(
                    amount=amount,
                    priority=priority,
                    msg_id=item.get('msg_id', None),
                    debtor_name=item.get('debtor_name', None),
                    creditor_name=item.get('creditor_name', None),
                    is_sovereign=item.get('is_sovereign', False),
                    cre_dt_tm=timestamp
                )
                messages.append(message)
            
            return messages
            
        except Exception as e:
            raise ValueError(f"Error parsing JSON: {str(e)}")
    
    def load_from_file(self, uploaded_file) -> List[ISO20022Message]:
        """
        Load payment data from uploaded file (auto-detect format).
        
        Args:
            uploaded_file: Streamlit uploaded file object
            
        Returns:
            List of ISO20022Message objects
        """
        file_content = uploaded_file.read()
        filename = uploaded_file.name.lower()
        
        if filename.endswith('.csv'):
            return self.load_from_csv(file_content, uploaded_file.name)
        elif filename.endswith('.json'):
            return self.load_from_json(file_content)
        else:
            raise ValueError(f"Unsupported file format. Please use CSV or JSON.")


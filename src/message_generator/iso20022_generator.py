"""
ISO 20022 XML Message Generator
Generates valid, mock ISO 20022 XML messages for simulation purposes.
Supports pacs.008 (Credit Transfer) and camt.053 (Bank Statement) messages.
"""

from datetime import datetime, timedelta
from typing import Optional
from lxml import etree
import uuid
from src.utils.models import ISO20022Message, PaymentType, PriorityTier


class ISO20022Generator:
    """Generator for ISO 20022 compliant XML messages."""
    
    # ISO 20022 Namespaces
    NAMESPACES = {
        'Document': 'urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08',
        'camt': 'urn:iso:std:iso:20022:tech:xsd:camt.053.001.08',
    }
    
    @staticmethod
    def generate_pacs008(
        amount: float,
        priority: PriorityTier = PriorityTier.NORMAL,
        msg_id: Optional[str] = None,
        end_to_end_id: Optional[str] = None,
        debtor_name: Optional[str] = None,
        creditor_name: Optional[str] = None,
        is_sovereign: bool = False,
        cre_dt_tm: Optional[datetime] = None
    ) -> ISO20022Message:
        """
        Generate a pacs.008 (Customer Credit Transfer) message.
        
        Args:
            amount: Transaction amount in USD
            priority: Payment priority tier
            msg_id: Optional message ID (auto-generated if not provided)
            end_to_end_id: Optional end-to-end ID (auto-generated if not provided)
            debtor_name: Name of the debtor/originator
            creditor_name: Name of the creditor/beneficiary
            is_sovereign: Whether this is a sovereign payment
            cre_dt_tm: Creation datetime (defaults to now)
            
        Returns:
            ISO20022Message object with raw XML
        """
        if msg_id is None:
            msg_id = f"BIS-LIQUEFLOW-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        if end_to_end_id is None:
            end_to_end_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        
        if cre_dt_tm is None:
            cre_dt_tm = datetime.now()
        
        if debtor_name is None:
            debtor_name = "ORIGINATOR_BANK" if not is_sovereign else "US_TREASURY"
        
        if creditor_name is None:
            creditor_name = "BENEFICIARY_BANK" if not is_sovereign else "FEDERAL_RESERVE"
        
        # Create XML structure
        root = etree.Element(
            "{urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08}Document",
            nsmap={'Document': 'urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08'}
        )
        
        fitoficstmrcdttrf = etree.SubElement(root, "FIToFICstmrCdtTrf")
        
        # Group Header
        grphdr = etree.SubElement(fitoficstmrcdttrf, "GrpHdr")
        msgid_elem = etree.SubElement(grphdr, "MsgId")
        msgid_elem.text = msg_id
        
        cre_dt_tm_elem = etree.SubElement(grphdr, "CreDtTm")
        cre_dt_tm_elem.text = cre_dt_tm.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Credit Transfer Transaction Information
        cdttrftxinf = etree.SubElement(fitoficstmrcdttrf, "CdtTrfTxInf")
        
        # Payment Identification
        pmtid = etree.SubElement(cdttrftxinf, "PmtId")
        endtoendid = etree.SubElement(pmtid, "EndToEndId")
        endtoendid.text = end_to_end_id
        
        # Instructed Amount
        intdamt = etree.SubElement(cdttrftxinf, "IntdAmt")
        intdamt.set("Ccy", "USD")
        intdamt.text = f"{amount:.2f}"
        
        # Debtor Information
        dbtr = etree.SubElement(cdttrftxinf, "Dbtr")
        dbtr_nm = etree.SubElement(dbtr, "Nm")
        dbtr_nm.text = debtor_name
        
        # Creditor Information
        cdtr = etree.SubElement(cdttrftxinf, "Cdtr")
        cdtr_nm = etree.SubElement(cdtr, "Nm")
        cdtr_nm.text = creditor_name
        
        # Priority (as proprietary field)
        if priority != PriorityTier.NORMAL:
            prtry = etree.SubElement(cdttrftxinf, "Prtry")
            prtry.text = priority.value
        
        # Convert to string - FIX: Use UTF-8 encoding then decode to avoid lxml error
        xml_bytes = etree.tostring(root, encoding='UTF-8', pretty_print=True, xml_declaration=True)
        xml_string = xml_bytes.decode('utf-8')
        
        # Create message object
        message = ISO20022Message(
            msg_id=msg_id,
            msg_type=PaymentType.PACS_008,
            cre_dt_tm=cre_dt_tm,
            priority=priority,
            amount=amount,
            currency="USD",
            end_to_end_id=end_to_end_id,
            debtor_name=debtor_name,
            creditor_name=creditor_name,
            is_sovereign=is_sovereign,
            raw_xml=xml_string
        )
        
        return message
    
    @staticmethod
    def generate_camt053(
        current_balance: float,
        msg_id: Optional[str] = None,
        cre_dt_tm: Optional[datetime] = None
    ) -> ISO20022Message:
        """
        Generate a camt.053 (Bank to Customer Statement) message.
        
        Args:
            current_balance: Current account balance
            msg_id: Optional message ID (auto-generated if not provided)
            cre_dt_tm: Creation datetime (defaults to now)
            
        Returns:
            ISO20022Message object with raw XML
        """
        if msg_id is None:
            msg_id = f"BIS-CAMT053-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        if cre_dt_tm is None:
            cre_dt_tm = datetime.now()
        
        # Create XML structure
        root = etree.Element(
            "{urn:iso:std:iso:20022:tech:xsd:camt.053.001.08}Document",
            nsmap={'camt': 'urn:iso:std:iso:20022:tech:xsd:camt.053.001.08'}
        )
        
        bk_to_cstmr_stmt = etree.SubElement(root, "BkToCstmrStmt")
        
        # Group Header
        grphdr = etree.SubElement(bk_to_cstmr_stmt, "GrpHdr")
        msgid_elem = etree.SubElement(grphdr, "MsgId")
        msgid_elem.text = msg_id
        
        cre_dt_tm_elem = etree.SubElement(grphdr, "CreDtTm")
        cre_dt_tm_elem.text = cre_dt_tm.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Statement
        stmt = etree.SubElement(bk_to_cstmr_stmt, "Stmt")
        
        # Account
        acct = etree.SubElement(stmt, "Acct")
        acct_id = etree.SubElement(acct, "Id")
        iban = etree.SubElement(acct_id, "IBAN")
        iban.text = "US64FRNY1234567890123456"
        
        # Balance
        bal = etree.SubElement(stmt, "Bal")
        tp = etree.SubElement(bal, "Tp")
        cd_or_prtry = etree.SubElement(tp, "CdOrPrtry")
        cd = etree.SubElement(cd_or_prtry, "Cd")
        cd.text = "CLBD"
        
        amt = etree.SubElement(bal, "Amt")
        amt.set("Ccy", "USD")
        amt.text = f"{current_balance:.2f}"
        
        dt = etree.SubElement(bal, "Dt")
        dt_tag = etree.SubElement(dt, "Dt")
        dt_tag.text = cre_dt_tm.strftime("%Y-%m-%d")
        
        # Convert to string - FIX: Use UTF-8 encoding then decode to avoid lxml error
        xml_bytes = etree.tostring(root, encoding='UTF-8', pretty_print=True, xml_declaration=True)
        xml_string = xml_bytes.decode('utf-8')
        
        # Create message object
        message = ISO20022Message(
            msg_id=msg_id,
            msg_type=PaymentType.CAMT_053,
            cre_dt_tm=cre_dt_tm,
            priority=PriorityTier.NORMAL,
            amount=current_balance,
            currency="USD",
            end_to_end_id=msg_id,
            raw_xml=xml_string
        )
        
        return message
    
    @staticmethod
    def validate_xml(xml_string: str) -> bool:
        """
        Validate XML structure (basic validation).
        In production, this would validate against ISO 20022 XSD schemas.
        
        Args:
            xml_string: XML string to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            etree.fromstring(xml_string.encode())
            return True
        except etree.XMLSyntaxError:
            return False

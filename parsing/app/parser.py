# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Email message parsing from mbox format."""

import mailbox
import email
import logging
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime
from typing import Dict, Any, List, Optional

from .normalizer import TextNormalizer
from .draft_detector import DraftDetector

logger = logging.getLogger(__name__)


class MessageParser:
    """Parses email messages from mbox format."""

    def __init__(
        self,
        normalizer: Optional[TextNormalizer] = None,
        draft_detector: Optional[DraftDetector] = None,
    ):
        """Initialize message parser.
        
        Args:
            normalizer: Text normalizer instance (creates default if None)
            draft_detector: Draft detector instance (creates default if None)
        """
        self.normalizer = normalizer or TextNormalizer()
        self.draft_detector = draft_detector or DraftDetector()

    def parse_mbox(self, mbox_path: str, archive_id: str) -> tuple[List[Dict[str, Any]], List[str]]:
        """Parse an mbox file and extract all messages.
        
        Args:
            mbox_path: Path to the mbox file
            archive_id: Archive identifier for tracking
            
        Returns:
            Tuple of (parsed_messages, errors) where errors is a list of error messages
        """
        parsed_messages = []
        errors = []

        try:
            mbox = mailbox.mbox(mbox_path)
            
            for idx, message in enumerate(mbox):
                try:
                    parsed = self.parse_message(message, archive_id)
                    if parsed:
                        parsed_messages.append(parsed)
                except Exception as e:
                    error_msg = f"Failed to parse message {idx}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
            
            logger.info(f"Parsed {len(parsed_messages)} messages from {mbox_path}")
            
        except Exception as e:
            error_msg = f"Failed to open mbox file {mbox_path}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        return parsed_messages, errors

    def parse_message(self, message: email.message.Message, archive_id: str) -> Optional[Dict[str, Any]]:
        """Parse a single email message.
        
        Args:
            message: Email message object
            archive_id: Archive identifier
            
        Returns:
            Parsed message dictionary or None if required fields are missing
        """
        # Extract message ID (required field)
        message_id = self._extract_message_id(message)
        if not message_id:
            logger.warning("Message missing Message-ID header, skipping")
            return None

        # Extract headers
        in_reply_to = self._extract_in_reply_to(message)
        references = self._parse_references(message.get("References", ""))
        subject = self._decode_header(message.get("Subject", ""))
        date = self._parse_date(message.get("Date"))
        
        # Extract addresses
        from_addr = self._parse_address(message.get("From", ""))
        to_addrs = self._parse_address_list(message.get("To", ""))
        cc_addrs = self._parse_address_list(message.get("CC", ""))
        
        # Extract body
        body_raw = self._extract_body(message)
        body_normalized = self.normalizer.normalize(body_raw)
        
        # Detect draft mentions
        draft_mentions = self.draft_detector.detect(body_normalized)
        
        # Determine thread_id (use in_reply_to if available, otherwise message_id)
        # This will be refined later by thread_builder
        thread_id = in_reply_to if in_reply_to else message_id
        
        # Build parsed message
        parsed = {
            "message_id": message_id,
            "archive_id": archive_id,
            "thread_id": thread_id,
            "in_reply_to": in_reply_to,
            "references": references,
            "subject": subject,
            "from": from_addr,
            "to": to_addrs,
            "cc": cc_addrs,
            "date": date,
            "body_raw": body_raw,
            "body_normalized": body_normalized,
            "headers": self._extract_extra_headers(message),
            "draft_mentions": draft_mentions,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        
        return parsed

    def _extract_message_id(self, message: email.message.Message) -> Optional[str]:
        """Extract and clean Message-ID header.
        
        Args:
            message: Email message
            
        Returns:
            Clean message ID without angle brackets, or None if missing
        """
        message_id = message.get("Message-ID", "")
        if message_id:
            # Remove angle brackets
            return message_id.strip("<>")
        return None

    def _extract_in_reply_to(self, message: email.message.Message) -> Optional[str]:
        """Extract In-Reply-To header.
        
        Args:
            message: Email message
            
        Returns:
            Clean in-reply-to ID or None
        """
        in_reply_to = message.get("In-Reply-To", "")
        if in_reply_to:
            return in_reply_to.strip("<>")
        return None

    def _parse_references(self, references_str: str) -> List[str]:
        """Parse References header into list of message IDs.
        
        Args:
            references_str: References header value
            
        Returns:
            List of message IDs
        """
        if not references_str:
            return []
        
        # Split on whitespace and remove angle brackets
        refs = references_str.split()
        return [ref.strip("<>") for ref in refs if ref]

    def _decode_header(self, header_value: str) -> str:
        """Decode email header value.
        
        Args:
            header_value: Raw header value
            
        Returns:
            Decoded header string
        """
        if not header_value:
            return ""
        
        try:
            decoded_parts = email.header.decode_header(header_value)
            parts = []
            for content, encoding in decoded_parts:
                if isinstance(content, bytes):
                    parts.append(content.decode(encoding or 'utf-8', errors='replace'))
                else:
                    parts.append(content)
            return ' '.join(parts)
        except Exception as e:
            logger.debug(f"Failed to decode header: {e}")
            return str(header_value)

    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse email date header to ISO 8601 format.
        
        Args:
            date_str: Date header value
            
        Returns:
            ISO 8601 formatted date string or None
        """
        if not date_str:
            return None
        
        try:
            dt = parsedate_to_datetime(date_str)
            # Convert to UTC and format as ISO 8601
            return dt.isoformat().replace("+00:00", "Z")
        except Exception as e:
            logger.debug(f"Failed to parse date '{date_str}': {e}")
            return None

    def _parse_address(self, addr_str: str) -> Optional[Dict[str, str]]:
        """Parse email address.
        
        Args:
            addr_str: Email address string (e.g., "Name <email@example.com>")
            
        Returns:
            Dictionary with 'name' and 'email' keys, or None if invalid
        """
        if not addr_str:
            return None
        
        try:
            # Decode the address string first
            addr_str = self._decode_header(addr_str)
            name, email_addr = parseaddr(addr_str)
            
            if email_addr:
                return {
                    "name": name or "",
                    "email": email_addr,
                }
        except Exception as e:
            logger.debug(f"Failed to parse address '{addr_str}': {e}")
        
        return None

    def _parse_address_list(self, addr_list_str: str) -> List[Dict[str, str]]:
        """Parse comma-separated list of email addresses.
        
        Args:
            addr_list_str: Comma-separated email addresses
            
        Returns:
            List of address dictionaries
        """
        if not addr_list_str:
            return []
        
        addresses = []
        # Split on commas, but be careful with commas in quoted names
        for addr_str in addr_list_str.split(','):
            addr = self._parse_address(addr_str.strip())
            if addr:
                addresses.append(addr)
        
        return addresses

    def _extract_body(self, message: email.message.Message) -> str:
        """Extract body text from email message.
        
        Args:
            message: Email message
            
        Returns:
            Body text (plain text preferred, HTML as fallback)
        """
        body = ""
        
        if message.is_multipart():
            # Prefer plain text over HTML
            for part in message.walk():
                content_type = part.get_content_type()
                
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            body = payload.decode(charset, errors='replace')
                            break
                    except Exception as e:
                        logger.debug(f"Failed to decode text/plain part: {e}")
            
            # If no plain text found, try HTML
            if not body:
                for part in message.walk():
                    content_type = part.get_content_type()
                    
                    if content_type == "text/html":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                charset = part.get_content_charset() or 'utf-8'
                                body = payload.decode(charset, errors='replace')
                                break
                        except Exception as e:
                            logger.debug(f"Failed to decode text/html part: {e}")
        else:
            # Simple message
            try:
                payload = message.get_payload(decode=True)
                if payload:
                    charset = message.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='replace')
                else:
                    # Fallback to string payload
                    body = str(message.get_payload())
            except Exception as e:
                logger.debug(f"Failed to decode message body: {e}")
                body = str(message.get_payload())
        
        return body

    def _extract_extra_headers(self, message: email.message.Message) -> Dict[str, str]:
        """Extract additional headers for metadata.
        
        Args:
            message: Email message
            
        Returns:
            Dictionary of extra headers
        """
        headers = {}
        
        # Headers we want to preserve
        preserve_headers = [
            "X-Mailer",
            "User-Agent",
            "Content-Type",
            "Content-Transfer-Encoding",
            "MIME-Version",
            "X-Priority",
            "Importance",
        ]
        
        for header in preserve_headers:
            value = message.get(header)
            if value:
                headers[header.lower()] = self._decode_header(value)
        
        return headers

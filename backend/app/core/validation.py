"""
Input validation and sanitization utilities.
Prevents injection attacks, path traversal, and other input-based vulnerabilities.
"""

import re
from typing import Optional
from pathlib import Path


class InputValidator:
    """Utilities for validating and sanitizing user input."""
    
    # Email validation regex (RFC 5322 compliant)
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    # Phone number regex (international format)
    PHONE_REGEX = re.compile(
        r'^\+?[1-9]\d{1,14}$'
    )
    
    # Allowed characters for file names
    FILENAME_SAFE_CHARS = set(
        'abcdefghijklmnopqrstuvwxyz'
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        '0123456789'
        '._- '
    )
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email address format.
        
        Args:
            email: Email address to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not email or len(email) > 320:  # RFC 5321
            return False
        
        return bool(InputValidator.EMAIL_REGEX.match(email))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """
        Validate phone number format.
        
        Args:
            phone: Phone number to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not phone:
            return False
        
        # Remove common separators
        cleaned = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        return bool(InputValidator.PHONE_REGEX.match(cleaned))
    
    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 255) -> str:
        """
        Sanitize a filename to prevent path traversal and other attacks.
        
        Args:
            filename: Original filename
            max_length: Maximum allowed length
            
        Returns:
            Sanitized filename
        """
        if not filename:
            return "unnamed"
        
        # Remove path separators
        filename = filename.replace('/', '_').replace('\\', '_')
        
        # Remove null bytes
        filename = filename.replace('\x00', '')
        
        # Keep only safe characters
        sanitized = ''.join(
            c if c in InputValidator.FILENAME_SAFE_CHARS else '_'
            for c in filename
        )
        
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        
        # Ensure not empty
        if not sanitized:
            sanitized = "unnamed"
        
        # Truncate to max length
        if len(sanitized) > max_length:
            # Try to preserve extension
            if '.' in sanitized:
                name, ext = sanitized.rsplit('.', 1)
                max_name_length = max_length - len(ext) - 1
                sanitized = name[:max_name_length] + '.' + ext
            else:
                sanitized = sanitized[:max_length]
        
        return sanitized
    
    @staticmethod
    def validate_file_path(file_path: str, allowed_base_paths: list) -> bool:
        """
        Validate that a file path is within allowed directories.
        Prevents path traversal attacks.
        
        Args:
            file_path: Path to validate
            allowed_base_paths: List of allowed base directories
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Resolve to absolute path
            resolved_path = Path(file_path).resolve()
            
            # Check if within any allowed base path
            for base_path in allowed_base_paths:
                resolved_base = Path(base_path).resolve()
                try:
                    resolved_path.relative_to(resolved_base)
                    return True
                except ValueError:
                    continue
            
            return False
        
        except (ValueError, OSError):
            return False
    
    @staticmethod
    def sanitize_sql_like_pattern(pattern: str) -> str:
        """
        Sanitize a string for use in SQL LIKE patterns.
        Escapes special LIKE characters.
        
        Args:
            pattern: Pattern to sanitize
            
        Returns:
            Sanitized pattern
        """
        # Escape special LIKE characters
        pattern = pattern.replace('\\', '\\\\')
        pattern = pattern.replace('%', '\\%')
        pattern = pattern.replace('_', '\\_')
        
        return pattern
    
    @staticmethod
    def validate_string_length(
        value: str,
        min_length: int = 0,
        max_length: int = None
    ) -> bool:
        """
        Validate string length constraints.
        
        Args:
            value: String to validate
            min_length: Minimum allowed length
            max_length: Maximum allowed length (None for no limit)
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(value, str):
            return False
        
        length = len(value)
        
        if length < min_length:
            return False
        
        if max_length is not None and length > max_length:
            return False
        
        return True
    
    @staticmethod
    def sanitize_html(text: str) -> str:
        """
        Basic HTML sanitization to prevent XSS.
        For production, consider using a library like bleach.
        
        Args:
            text: Text that may contain HTML
            
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        # Replace dangerous characters
        replacements = {
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '&': '&amp;',
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        
        return text
    
    @staticmethod
    def validate_uuid(uuid_string: str) -> bool:
        """
        Validate UUID format.
        
        Args:
            uuid_string: UUID string to validate
            
        Returns:
            True if valid UUID, False otherwise
        """
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        
        return bool(uuid_pattern.match(uuid_string))
    
    @staticmethod
    def validate_url(url: str, allowed_schemes: list = None) -> bool:
        """
        Validate URL format and scheme.
        
        Args:
            url: URL to validate
            allowed_schemes: List of allowed schemes (e.g., ['http', 'https'])
            
        Returns:
            True if valid, False otherwise
        """
        if not url:
            return False
        
        url_pattern = re.compile(
            r'^(https?):\/\/'  # Scheme
            r'([a-zA-Z0-9.-]+)'  # Domain
            r'(:[0-9]+)?'  # Optional port
            r'(\/[^\s]*)?$'  # Optional path
        )
        
        match = url_pattern.match(url)
        if not match:
            return False
        
        # Check allowed schemes
        if allowed_schemes:
            scheme = match.group(1)
            if scheme not in allowed_schemes:
                return False
        
        return True


class PasswordPolicy:
    """Password validation and policy enforcement."""
    
    # Minimum password requirements
    MIN_LENGTH = 12
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True
    SPECIAL_CHARS = '!@#$%^&*()_+-=[]{}|;:,.<>?'
    
    # Common weak passwords to reject
    COMMON_PASSWORDS = {
        'password', 'password123', '12345678', 'qwerty', 'abc123',
        'password1', '123456789', '1234567890', 'admin', 'letmein',
        'welcome', 'monkey', '1234', 'iloveyou', 'password!',
        'Password1', 'Password123', 'Admin123', 'Welcome1'
    }
    
    @classmethod
    def validate_password(cls, password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password against policy.
        
        Args:
            password: Password to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not password:
            return False, "Password is required"
        
        # Check length
        if len(password) < cls.MIN_LENGTH:
            return False, f"Password must be at least {cls.MIN_LENGTH} characters long"
        
        # Check maximum length (prevent DoS)
        if len(password) > 128:
            return False, "Password is too long (maximum 128 characters)"
        
        # Check for common weak passwords
        if password.lower() in cls.COMMON_PASSWORDS:
            return False, "Password is too common. Please choose a stronger password"
        
        # Check uppercase requirement
        if cls.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        # Check lowercase requirement
        if cls.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        # Check digit requirement
        if cls.REQUIRE_DIGIT and not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        
        # Check special character requirement
        if cls.REQUIRE_SPECIAL and not any(c in cls.SPECIAL_CHARS for c in password):
            return False, f"Password must contain at least one special character ({cls.SPECIAL_CHARS})"
        
        # Check for sequential characters
        if cls._has_sequential_chars(password):
            return False, "Password contains sequential characters (e.g., 123, abc)"
        
        # Check for repeated characters
        if cls._has_repeated_chars(password):
            return False, "Password contains too many repeated characters"
        
        return True, None
    
    @staticmethod
    def _has_sequential_chars(password: str, max_sequential: int = 3) -> bool:
        """Check if password has sequential characters."""
        password_lower = password.lower()
        
        for i in range(len(password_lower) - max_sequential + 1):
            chunk = password_lower[i:i + max_sequential]
            
            # Check for sequential numbers
            if chunk.isdigit():
                digits = [int(d) for d in chunk]
                if all(digits[j] + 1 == digits[j + 1] for j in range(len(digits) - 1)):
                    return True
            
            # Check for sequential letters
            if chunk.isalpha():
                if all(ord(chunk[j]) + 1 == ord(chunk[j + 1]) for j in range(len(chunk) - 1)):
                    return True
        
        return False
    
    @staticmethod
    def _has_repeated_chars(password: str, max_repeated: int = 3) -> bool:
        """Check if password has too many repeated characters."""
        for i in range(len(password) - max_repeated + 1):
            if len(set(password[i:i + max_repeated])) == 1:
                return True
        
        return False
    
    @staticmethod
    def generate_password_strength_score(password: str) -> int:
        """
        Calculate password strength score (0-100).
        
        Args:
            password: Password to score
            
        Returns:
            Strength score from 0 (very weak) to 100 (very strong)
        """
        score = 0
        
        # Length score (up to 30 points)
        score += min(len(password) * 2, 30)
        
        # Character variety (up to 40 points)
        if any(c.isupper() for c in password):
            score += 10
        if any(c.islower() for c in password):
            score += 10
        if any(c.isdigit() for c in password):
            score += 10
        if any(c in PasswordPolicy.SPECIAL_CHARS for c in password):
            score += 10
        
        # Uniqueness (up to 30 points)
        unique_chars = len(set(password))
        score += min(unique_chars * 2, 30)
        
        # Penalize common patterns
        if password.lower() in PasswordPolicy.COMMON_PASSWORDS:
            score = min(score, 20)
        
        return min(score, 100)


# Export validators
__all__ = ["InputValidator", "PasswordPolicy"]

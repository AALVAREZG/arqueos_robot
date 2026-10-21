"""
SICAL Security Module (arqueo) - Token-based duplicate confirmation.

Port of the gastos_robot confirmation-token flow, reduced to what the arqueo
consumer needs. Without this module the arqueo consumer could only ever abort
on a duplicate: it reported P_DUPLICATED but issued no token, so sical-robot's
"Confirm duplicate" action failed with "No duplicate confirmation token found".

Two-phase flow:
  Phase 1 (duplicate_policy='check_only')  - SICAL is searched for similar
      operations. If any are found the operation is aborted and a confirmation
      token is returned to the producer alongside P_DUPLICATED.
  Phase 2 (duplicate_policy='force_create') - the producer resends the same
      operation with that token. The token is validated (exists / not expired /
      not already used / hash matches the operation data) and, if valid, the
      duplicate check is skipped and the operation proceeds.

Security properties:
- Tokens are cryptographically tied to the operation data (HMAC-SHA256), so a
  token cannot be reused for a different operation.
- Tokens are single-use, which prevents replaying one confirmation to create
  the same operation repeatedly.
- Tokens expire (see DUPLICATE_TOKEN_LIFETIME_SECONDS in config.py).

Caveat: the token store lives in this process's memory. Restarting the consumer
invalidates every outstanding token, and the producer has to re-run Phase 1.
"""

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from logging_setup import (
    get_logger, phase as log_phase, ok as log_ok,
    warn as log_warn, fail as log_fail,
)

logger = get_logger(__name__)

try:
    from config import DUPLICATE_TOKEN_LIFETIME_SECONDS as _DEFAULT_LIFETIME
except ImportError:  # config not importable (e.g. standalone unit test)
    _DEFAULT_LIFETIME = 3600


@dataclass
class ConfirmationToken:
    """A single-use confirmation token tied to one arqueo operation."""
    token_id: str
    operation_hash: str
    created_at: float
    expires_at: float
    used: bool = False
    caja: Optional[str] = None
    fecha: Optional[str] = None


class DuplicateConfirmationManager:
    """Issues and validates confirmation tokens for force_create arqueos."""

    def __init__(self, token_lifetime_seconds: int = _DEFAULT_LIFETIME,
                 secret_key: Optional[str] = None):
        self.token_lifetime = token_lifetime_seconds
        # Per-process key: the token store is in-memory anyway, so a restart
        # consistently invalidates both the key and every token it signed.
        self.secret_key = secret_key or secrets.token_hex(32)
        self.tokens: Dict[str, ConfirmationToken] = {}
        self._cleanup_interval = 60
        self._last_cleanup = time.time()

        log_phase(logger, 'SECURITY',
                  f'confirmation manager ready (token lifetime '
                  f'{token_lifetime_seconds}s)')

    def generate_token(self, operation_data: Dict[str, Any]) -> Tuple[str, float]:
        """
        Issue a confirmation token for an operation flagged as duplicate.

        Args:
            operation_data: the arqueo `detalle` the token is bound to. Must be
                the same dict the producer will resend in Phase 2, otherwise
                validation fails on the hash comparison.

        Returns:
            (token_id, expires_at_unix_timestamp)
        """
        operation_hash = self._hash_operation_data(operation_data)
        token_id = secrets.token_urlsafe(32)

        now = time.time()
        expires_at = now + self.token_lifetime

        self.tokens[token_id] = ConfirmationToken(
            token_id=token_id,
            operation_hash=operation_hash,
            created_at=now,
            expires_at=expires_at,
            used=False,
            caja=operation_data.get('caja'),
            fecha=operation_data.get('fecha'),
        )

        log_phase(logger, 'SECURITY',
                  f'issued confirmation token {token_id[:16]}... for '
                  f'caja={operation_data.get("caja")} '
                  f'fecha={operation_data.get("fecha")}, '
                  f'expires in {self.token_lifetime}s')

        self._cleanup_expired_tokens()

        return token_id, expires_at

    def validate_token(self, token_id: Optional[str],
                       operation_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate and consume a confirmation token.

        Returns (True, '') when the token is valid; (False, reason) otherwise.
        A valid token is marked used before returning, so a second call with the
        same token fails.
        """
        if not token_id:
            log_warn(logger, 'SECURITY', 'force_create without a token')
            return False, ('Missing confirmation token - force_create requires '
                           'a valid token from the duplicate check')

        token = self.tokens.get(token_id)
        if token is None:
            log_warn(logger, 'SECURITY',
                     f'unknown token {token_id[:16]}... (expired, already '
                     f'cleaned up, or consumer restarted)')
            return False, ('Invalid confirmation token - not found. Re-run the '
                           'duplicate check to obtain a new one')

        if token.used:
            log_warn(logger, 'SECURITY',
                     f'replay detected - token {token_id[:16]}... already used')
            return False, ('Confirmation token already used - each token is '
                           'valid for a single operation')

        now = time.time()
        if now > token.expires_at:
            age = now - token.created_at
            log_warn(logger, 'SECURITY',
                     f'expired token {token_id[:16]}... '
                     f'(age {age:.0f}s, max {self.token_lifetime}s)')
            return False, (f'Confirmation token expired - tokens are valid for '
                           f'{self.token_lifetime} seconds')

        operation_hash = self._hash_operation_data(operation_data)
        if operation_hash != token.operation_hash:
            log_fail(logger, 'SECURITY',
                     f'hash mismatch for token {token_id[:16]}... - the '
                     f'operation data changed since the duplicate check')
            return False, ('Confirmation token does not match the operation '
                           'data - possible tampering')

        token.used = True
        log_ok(logger, 'SECURITY',
               f'token {token_id[:16]}... validated '
               f'({token.expires_at - now:.0f}s remaining)')

        return True, ''

    def _hash_operation_data(self, operation_data: Dict[str, Any]) -> str:
        """
        Deterministic HMAC-SHA256 over the fields that identify an arqueo.

        Only stable, identity-bearing fields are hashed. Volatile ones (such as
        `metadata.generation_datetime`) are excluded so that a Phase 2 resend of
        the same operation still matches.
        """
        key_fields = {
            'tercero': operation_data.get('tercero'),
            'fecha': operation_data.get('fecha'),
            'caja': operation_data.get('caja'),
            'naturaleza': operation_data.get('naturaleza'),
            'aplicaciones': [
                {
                    'economica': app.get('economica'),
                    'importe': str(app.get('importe')),
                }
                for app in operation_data.get('aplicaciones', [])
            ],
        }

        json_str = json.dumps(key_fields, sort_keys=True, separators=(',', ':'))

        return hmac.new(
            self.secret_key.encode(),
            json_str.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _cleanup_expired_tokens(self) -> None:
        """Drop expired tokens periodically so the store cannot grow forever."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        expired = [tid for tid, t in self.tokens.items() if now > t.expires_at]
        for tid in expired:
            del self.tokens[tid]

        self._last_cleanup = now

        if expired:
            log_phase(logger, 'SECURITY',
                      f'cleaned up {len(expired)} expired token(s)')


_confirmation_manager: Optional[DuplicateConfirmationManager] = None


def get_confirmation_manager() -> DuplicateConfirmationManager:
    """Return the process-wide confirmation manager, creating it on first use."""
    global _confirmation_manager
    if _confirmation_manager is None:
        _confirmation_manager = DuplicateConfirmationManager()
    return _confirmation_manager


def audit_log_force_create(operation_data: Dict[str, Any], is_valid: bool,
                           error_msg: str = '') -> None:
    """Record every force_create attempt, accepted or rejected."""
    token_id = operation_data.get('duplicate_confirmation_token') or ''
    summary = (f'caja={operation_data.get("caja")} '
               f'fecha={operation_data.get("fecha")} '
               f'tercero={operation_data.get("tercero")} '
               f'token={token_id[:16] + "..." if token_id else "MISSING"}')

    if is_valid:
        log_ok(logger, 'AUDIT', f'force_create ACCEPTED - {summary}')
    else:
        log_fail(logger, 'AUDIT',
                 f'force_create REJECTED - {summary} - {error_msg}')

"""
Authentication dependencies: resolve the current athlete or official from the
Bearer JWT, and enforce account-type authorization.
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import decode_access_token
from app.models.db_models import Athlete, Official

# auto_error=False so we can raise our own 401 with a friendly message.
_bearer = HTTPBearer(auto_error=False)


def _claims(creds: HTTPAuthorizationCredentials) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    claims = decode_access_token(creds.credentials)
    if not claims:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")
    return claims


def get_current_athlete(creds: HTTPAuthorizationCredentials = Depends(_bearer),
                        db: Session = Depends(get_db)) -> Athlete:
    claims = _claims(creds)
    if claims.get("typ") != "athlete":
        raise HTTPException(status_code=403, detail="This action requires an athlete account.")
    athlete = db.query(Athlete).filter(Athlete.athlete_id == claims.get("sub")).first()
    if not athlete:
        raise HTTPException(status_code=401, detail="Account no longer exists.")
    return athlete


def get_current_official(creds: HTTPAuthorizationCredentials = Depends(_bearer),
                         db: Session = Depends(get_db)) -> Official:
    claims = _claims(creds)
    if claims.get("typ") != "official":
        raise HTTPException(status_code=403, detail="This action requires an official / scout account.")
    official = db.query(Official).filter(Official.official_id == claims.get("sub")).first()
    if not official:
        raise HTTPException(status_code=401, detail="Account no longer exists.")
    return official


def get_athlete_or_official(creds: HTTPAuthorizationCredentials = Depends(_bearer),
                            db: Session = Depends(get_db)) -> dict:
    """Resolve either account type. Returns {'typ', 'athlete'|'official', 'id'}."""
    claims = _claims(creds)
    typ = claims.get("typ")
    sub = claims.get("sub")
    if typ == "official":
        official = db.query(Official).filter(Official.official_id == sub).first()
        if not official:
            raise HTTPException(status_code=401, detail="Account no longer exists.")
        return {"typ": "official", "official": official, "id": sub}
    if typ == "athlete":
        athlete = db.query(Athlete).filter(Athlete.athlete_id == sub).first()
        if not athlete:
            raise HTTPException(status_code=401, detail="Account no longer exists.")
        return {"typ": "athlete", "athlete": athlete, "id": sub}
    raise HTTPException(status_code=401, detail="Invalid token.")

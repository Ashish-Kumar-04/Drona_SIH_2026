"""
Database Models for Athlete, Assessment, and Performance Index tables.
Matches the official SIH 25073 specification (Document Section 20).
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Athlete(Base):
    __tablename__ = "athletes"

    athlete_id = Column(String(50), primary_key=True, index=True) # e.g. ATH-2026-000123
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    category = Column(String(20), nullable=False, default="Male") # Male, Female, General
    state = Column(String(50), nullable=False)
    district = Column(String(50), nullable=False)
    school = Column(String(100), nullable=True)
    sports_interest = Column(String(100), nullable=True)
    height_cm = Column(Float, nullable=True)  # Height in cm for jump scaling
    weight_kg = Column(Float, nullable=True)  # Weight in kg
    phone = Column(String(20), nullable=True)  # Contact phone
    email = Column(String(100), nullable=True)  # Contact email
    password_hash = Column(String(128), nullable=False)  # SHA-256 hashed password
    created_at = Column(DateTime, default=datetime.utcnow)

    assessments = relationship("Assessment", back_populates="athlete", cascade="all, delete-orphan")
    performance = relationship("Performance", back_populates="athlete", uselist=False, cascade="all, delete-orphan")


class OTPReset(Base):
    """Temporary OTP storage for password reset flow."""
    __tablename__ = "otp_resets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    athlete_id = Column(String(50), ForeignKey("athletes.athlete_id"), nullable=False)
    otp_code = Column(String(6), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used = Column(Integer, default=0)  # 0 = unused, 1 = used


class Assessment(Base):
    __tablename__ = "assessments"

    assessment_id = Column(String(50), primary_key=True, index=True)
    athlete_id = Column(String(50), ForeignKey("athletes.athlete_id"), nullable=False)
    test_type = Column(String(30), nullable=False) # sit_up, vertical_jump, shuttle_run
    raw_score = Column(Float, nullable=False) # e.g., reps count, jump height in cm, time in sec
    normalized_score = Column(Float, nullable=False) # 0-100 score
    confidence = Column(Float, nullable=False) # 0-100 % AI confidence score
    validation_score = Column(Float, nullable=False) # 0-100 % authenticity score
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), nullable=False, default="VALID") # VALID, SUSPICIOUS, INVALID
    sync_status = Column(String(20), nullable=False, default="SYNCED") # PENDING, SYNCED
    details_json = Column(Text, nullable=True) # Raw biomechanical breakdown details

    athlete = relationship("Athlete", back_populates="assessments")


class Performance(Base):
    __tablename__ = "performances"

    athlete_id = Column(String(50), ForeignKey("athletes.athlete_id"), primary_key=True)
    speed_score = Column(Float, nullable=False, default=0.0)
    agility_score = Column(Float, nullable=False, default=0.0)
    strength_score = Column(Float, nullable=False, default=0.0)
    power_score = Column(Float, nullable=False, default=0.0)
    endurance_score = Column(Float, nullable=False, default=0.0)
    flexibility_score = Column(Float, nullable=False, default=0.0)         # sit & reach domain
    body_composition_score = Column(Float, nullable=False, default=0.0)    # BMI-based indicator
    overall_index = Column(Float, nullable=False, default=0.0) # Athletic Performance Index
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    athlete = relationship("Athlete", back_populates="performance")


class Official(Base):
    """Scout / SAI official account — separate from athletes, with its own login."""
    __tablename__ = "officials"

    official_id = Column(String(50), primary_key=True, index=True)  # e.g. OFF-2026-000123
    name = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False, unique=True, index=True)  # login identifier
    organization = Column(String(120), nullable=True)  # e.g. Sports Authority of India
    phone = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)  # bcrypt hash
    created_at = Column(DateTime, default=datetime.utcnow)


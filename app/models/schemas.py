"""
Pydantic schemas for request validation and API responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class AthleteRegister(BaseModel):
    name: str
    age: int = Field(..., ge=6, le=60)
    category: str = Field("Male", description="Male, Female, or General")
    state: str
    district: str
    school: Optional[str] = None
    sports_interest: Optional[str] = None
    height_cm: Optional[float] = Field(None, ge=50, le=250, description="Height in cm")
    weight_kg: Optional[float] = Field(None, ge=10, le=200, description="Weight in kg")
    phone: Optional[str] = None
    email: Optional[str] = None
    password: str = Field(..., min_length=4, description="Account password")

class AthleteLogin(BaseModel):
    athlete_id: str
    password: str

class AthleteResponse(BaseModel):
    athlete_id: str
    name: str
    age: int
    category: str
    state: str
    district: str
    school: Optional[str]
    sports_interest: Optional[str]
    height_cm: Optional[float]
    weight_kg: Optional[float]
    phone: Optional[str]
    email: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# OTP Password Reset Schemas
class OTPRequestSchema(BaseModel):
    athlete_id: str

class OTPVerifySchema(BaseModel):
    athlete_id: str
    otp_code: str
    new_password: str = Field(..., min_length=4)

class Keypoint2D(BaseModel):
    x: float
    y: float
    visibility: float = 1.0

class LandmarkFrame(BaseModel):
    frame_index: int
    timestamp: float # in seconds
    landmarks: Dict[str, Keypoint2D] # landmark_name -> keypoint

class VideoAssessmentRequest(BaseModel):
    athlete_id: str
    test_type: str # sit_up, vertical_jump, shuttle_run
    fps: float = 30.0
    frames: List[LandmarkFrame]
    reference_height_cm: Optional[float] = 170.0 # for scale ratio if available

class AssessmentResponse(BaseModel):
    assessment_id: str
    athlete_id: str
    test_type: str
    raw_score: float
    unit: str
    normalized_score: float
    confidence: float
    validation_score: float
    status: str
    benchmark_status: str
    benchmark_source: str
    timestamp: datetime
    details: Dict[str, Any]

    class Config:
        from_attributes = True

class PerformanceResponse(BaseModel):
    athlete_id: str
    speed_score: float
    agility_score: float
    strength_score: float
    power_score: float
    endurance_score: float
    overall_index: float

    class Config:
        from_attributes = True

class AthleteProfileResponse(BaseModel):
    athlete: AthleteResponse
    performance: Optional[PerformanceResponse]
    recent_assessments: List[AssessmentResponse]

class SyncAssessmentItem(BaseModel):
    assessment_id: str
    athlete_id: str
    test_type: str
    raw_score: float
    normalized_score: float
    confidence: float
    validation_score: float
    timestamp: datetime
    status: str
    details_json: Optional[str] = None

class ScoutSearchRequest(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    min_overall_index: Optional[float] = None
    test_type: Optional[str] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None

from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Any

class KeystrokeEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    key: Optional[str] = None
    hold_time: Optional[float] = None
    flight_time: Optional[float] = None
    timestamp: Optional[float] = None
    pressure: Optional[float] = None
    dwell_time: Optional[float] = None
    ts: Optional[float] = None
    count: Optional[int] = None

class MouseEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    type: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    duration: Optional[float] = None
    timestamp: Optional[float] = None
    button: Optional[int] = None
    ts: Optional[float] = None
    count: Optional[int] = None

class TouchEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    type: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    pressure: Optional[float] = None
    area: Optional[float] = None
    timestamp: Optional[float] = None
    ts: Optional[float] = None

class ScrollEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    x: Optional[float] = None
    y: Optional[float] = None
    delta_x: Optional[float] = None
    delta_y: Optional[float] = None
    timestamp: Optional[float] = None
    ts: Optional[float] = None

class MotionEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    alpha: Optional[float] = None
    beta: Optional[float] = None
    gamma: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    timestamp: Optional[float] = None
    ts: Optional[float] = None

class CognitiveEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    hesitation_duration: Optional[float] = None
    correction_count: Optional[int] = None
    error_rate: Optional[float] = None
    timestamp: Optional[float] = None
    ts: Optional[float] = None

class NavigationEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    path: Optional[str] = None
    timestamp: Optional[float] = None
    ts: Optional[float] = None

class ExtendedFeaturesSchema(BaseModel):
    model_config = {'extra': 'allow'}
    touch_event_count: Optional[int] = 0
    touch_force_mean: Optional[float] = 0.5
    touch_area_mean: Optional[float] = 15.0
    touch_velocity_mean: Optional[float] = 0.5
    
    scroll_event_count: Optional[int] = 0
    scroll_velocity_mean: Optional[float] = 1.0
    scroll_velocity_std: Optional[float] = 0.5
    scroll_reversal_rate: Optional[float] = 0.2
    
    nav_dwell_mean: Optional[Any] = 1000.0
    nav_field_revisit_count: Optional[int] = 0
    nav_focus_sequence_entropy: Optional[float] = 1.0
    
    copy_paste_count: Optional[int] = 0
    correction_rate: Optional[float] = 0.1
    tab_switch_count: Optional[int] = 0
    hesitation_count: Optional[int] = 0
    hesitation_duration_mean: Optional[float] = 0.0
    reread_count: Optional[int] = 0
    rapid_submit_detected: Optional[Any] = 0
    
    motion_event_count: Optional[int] = 0
    motion_acc_std: Optional[float] = 1.0

class BehavioralPayloadSchema(BaseModel):
    session_id: Optional[str] = ""
    type: Optional[str] = "keystroke"
    event_count: Optional[int] = 1
    events: Optional[List[MouseEventSchema]] = Field(default=[])
    extended_features: Optional[ExtendedFeaturesSchema] = Field(default_factory=ExtendedFeaturesSchema)
    keystroke_events: Optional[List[KeystrokeEventSchema]] = Field(default=[])
    touch_events: Optional[List[TouchEventSchema]] = Field(default=[])
    scroll_events: Optional[List[ScrollEventSchema]] = Field(default=[])
    cognitive_events: Optional[List[CognitiveEventSchema]] = Field(default=[])
    motion_events: Optional[List[MotionEventSchema]] = Field(default=[])
    navigation_events: Optional[List[NavigationEventSchema]] = Field(default=[])
    keystroke_profile: Optional[Any] = Field(default=None)

    @model_validator(mode="after")
    def limit_arrays(self) -> "BehavioralPayloadSchema":
        for attr in ["events", "keystroke_events", "touch_events", "scroll_events", "cognitive_events", "motion_events", "navigation_events"]:
            lst = getattr(self, attr)
            if lst and len(lst) > 500:
                raise ValueError(f"Array '{attr}' exceeds maximum limit of 500 items")
        return self

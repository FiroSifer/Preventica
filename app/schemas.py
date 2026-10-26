import re
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, model_validator, field_validator
from .safety.geometry import validate_polygon

class CameraInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    location: str = Field(default='', max_length=200)
    source_type: Literal['usb','network','demo']
    source: str = Field(min_length=1, max_length=2048)
    enabled: bool = True
    @model_validator(mode='after')
    def valid(self):
        if self.source_type=='usb' and (not self.source.isdigit() or int(self.source)>99):
            raise ValueError('USB source must be an index from 0 to 99')
        if self.source_type=='demo' and self.source not in ('synthetic','offline'):
            raise ValueError('Demo source must be synthetic or offline')
        if self.source_type=='network':
            if self.source.startswith('env:'):
                if not re.fullmatch(r'env:[A-Za-z_][A-Za-z0-9_]*', self.source): raise ValueError('Invalid environment reference')
            else:
                u=urlsplit(self.source)
                if u.scheme not in ('rtsp','rtsps','http','https') or not u.hostname: raise ValueError('Use RTSP/HTTP URL or env:VARIABLE')
                if u.username or u.password: raise ValueError('Use env:VARIABLE for credential-bearing URLs')
        return self

class CameraPatch(BaseModel):
    name: str | None = None
    location: str | None = None
    source_type: Literal['usb','network','demo'] | None = None
    source: str | None = None
    enabled: bool | None = None

class ZoneInput(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    type: Literal['danger','restricted','warning','custom'] = 'restricted'
    severity: Literal['info','warning','critical'] = 'critical'
    enabled: bool = True
    polygon: list[list[float]]
    required_ppe: list[Literal['helmet','vest','gloves','boots']] = Field(default_factory=list)
    description: str = Field(default='',max_length=2000)
    @field_validator('polygon')
    @classmethod
    def polygon_valid(cls, v): return validate_polygon(v)
